"""
TTScraper - Main browser automation class for TikTok data extraction.

Provides a unified, user-friendly interface for creating and managing
a nodriver (async CDP) browser session configured for TikTok scraping,
with integrated network monitoring, rate limiting, and logging.

Usage:
    import asyncio
    from TTScraper import TTScraper

    async def main():
        scraper = TTScraper(headless=True)
        tab = await scraper.start_browser()
        # ... scrape TikTok data ...
        scraper.close()

    asyncio.run(main())
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import nodriver as uc

from config.settings import (
    BrowserConfig,
    NetworkConfig,
    ScrapingConfig,
    TTScraperConfig,
    DEFAULT_CONFIG,
)
from core.logging_config import get_logger
from core.rate_limiting import RateLimiter, RequestThrottler
from browser.network import NetworkMonitor


class TTScraper:
    """
    Main browser automation class for TikTok scraping.

    Wraps ``nodriver`` and integrates configuration,
    network monitoring (CDP), rate limiting, and logging into a single
    entry-point that the rest of the project consumes.

    Parameters
    ----------
    headless : bool
        Run Chrome in headless mode.
    user_data_dir : str | None
        Path to a Chrome user-data directory.
    profile_directory : str
        Chrome profile directory name (e.g. ``"Default"``).
    proxy : str | None
        Proxy string, e.g. ``"http://host:port"`` or ``"socks5://host:port"``.
    window_size : tuple[int, int]
        Browser window dimensions ``(width, height)``.
    user_agent : str | None
        Custom User-Agent string.  ``None`` keeps the browser default.
    disable_images : bool
        Block image loading for faster page loads.
    disable_javascript : bool
        Disable JavaScript execution.
    no_sandbox : bool
        Pass ``--no-sandbox`` to Chrome.
    disable_dev_shm_usage : bool
        Pass ``--disable-dev-shm-usage`` to Chrome.
    disable_gpu : bool
        Pass ``--disable-gpu`` to Chrome.
    disable_web_security : bool
        Pass ``--disable-web-security`` to Chrome.
    disable_features : str
        Comma-separated Chrome features to disable.
    enable_logging : bool
        Enable Chrome's internal logging.
    log_level : int
        Chrome log-level (0 = INFO … 3 = FATAL).
    arguments : list[str] | None
        Extra command-line arguments passed to Chrome.
    binary_location : str | None
        Path to a custom Chrome / Chromium binary.
    config : TTScraperConfig | None
        A full ``TTScraperConfig`` object.  Explicit keyword arguments
        always take precedence over values in *config*.
    """

    def __init__(
        self,
        *,
        headless: Optional[bool] = None,
        user_data_dir: Optional[str] = None,
        profile_directory: Optional[str] = None,
        proxy: Optional[str] = None,
        window_size: Optional[tuple] = None,
        user_agent: Optional[str] = None,
        disable_images: bool = False,
        disable_javascript: bool = False,
        no_sandbox: Optional[bool] = None,
        disable_dev_shm_usage: Optional[bool] = None,
        disable_gpu: bool = False,
        disable_web_security: bool = False,
        disable_features: Optional[str] = None,
        enable_logging: bool = False,
        log_level: int = 0,
        arguments: Optional[List[str]] = None,
        binary_location: Optional[str] = None,
        config: Optional[TTScraperConfig] = None,
    ) -> None:
        # ── configuration ────────────────────────────────────────────
        self._base_config: TTScraperConfig = config or DEFAULT_CONFIG

        # Store every explicit kwarg so start_browser can merge them later
        self._kwargs: Dict[str, Any] = {
            "headless": headless,
            "user_data_dir": user_data_dir,
            "profile_directory": profile_directory,
            "proxy": proxy,
            "window_size": window_size,
            "user_agent": user_agent,
            "disable_images": disable_images,
            "disable_javascript": disable_javascript,
            "no_sandbox": no_sandbox,
            "disable_dev_shm_usage": disable_dev_shm_usage,
            "disable_gpu": disable_gpu,
            "disable_web_security": disable_web_security,
            "disable_features": disable_features,
            "enable_logging": enable_logging,
            "log_level": log_level,
            "arguments": arguments,
            "binary_location": binary_location,
        }

        # ── logging ──────────────────────────────────────────────────
        self.logger: logging.Logger = get_logger("TTScraper")

        # ── rate limiting ────────────────────────────────────────────
        self.rate_limiter = RateLimiter(logger=self.logger)
        self.throttler = RequestThrottler(
            min_delay=self._base_config.scraping.rate_limit_delay
            if self._base_config.scraping
            else 2.0,
            logger=self.logger,
        )

        # ── state ────────────────────────────────────────────────────
        self.browser: Optional[uc.Browser] = None
        self.tab: Optional[uc.Tab] = None
        self.network_monitor: Optional[NetworkMonitor] = None

    # ------------------------------------------------------------------ #
    #  Resolve helpers                                                     #
    # ------------------------------------------------------------------ #

    def _resolve(self, key: str, fallback: Any = None) -> Any:
        """Return the kwarg value if explicitly set, else the config value, else *fallback*."""
        value = self._kwargs.get(key)
        if value is not None:
            return value
        return fallback

    # ------------------------------------------------------------------ #
    #  Browser lifecycle                                                   #
    # ------------------------------------------------------------------ #

    async def start_browser(
        self,
        url: str = "https://www.tiktok.com/",
        **overrides: Any,
    ) -> uc.Tab:
        """
        Create a nodriver browser, apply all configuration, and
        navigate to *url*.

        Any keyword passed here overrides both the constructor kwargs **and**
        the ``TTScraperConfig`` defaults.

        Parameters
        ----------
        url : str
            The initial URL to navigate to (default: TikTok home).
        **overrides
            Ad-hoc overrides identical to the constructor parameters.

        Returns
        -------
        nodriver.Tab
            The live Tab instance (equivalent to a page).
        """
        if self.browser is not None:
            self.logger.warning("Browser already running – closing the existing one first.")
            self.close()

        # Merge: overrides  >  constructor kwargs  >  config defaults
        merged = {**self._kwargs, **overrides}

        browser_cfg: BrowserConfig = self._base_config.browser or BrowserConfig()
        scraping_cfg: ScrapingConfig = self._base_config.scraping or ScrapingConfig()
        network_cfg: NetworkConfig = self._base_config.network or NetworkConfig()

        # ── Build browser_args list ──────────────────────────────────
        # Only add args the user explicitly requested.  nodriver already
        # ships its own sensible defaults so we don't inject anything extra.
        browser_args: List[str] = []

        # Window size
        w, h = merged.get("window_size") or browser_cfg.window_size or (1920, 1080)

        # Proxy
        proxy = merged.get("proxy")
        if proxy:
            browser_args.append(f"--proxy-server={proxy}")

        # ── Boolean flags → Chrome arguments (only when explicitly True) ─
        _flag_map = {
            "no_sandbox": "--no-sandbox",
            "disable_dev_shm_usage": "--disable-dev-shm-usage",
            "disable_gpu": "--disable-gpu",
            "disable_web_security": "--disable-web-security",
        }
        for kwarg_key, chrome_arg in _flag_map.items():
            if merged.get(kwarg_key) is True:
                browser_args.append(chrome_arg)

        # Disable features
        disable_features = merged.get("disable_features")
        if disable_features:
            browser_args.append(f"--disable-features={disable_features}")

        # Anti-automation stealth (only if explicitly configured)
        blink_features = browser_cfg.disable_blink_features
        if blink_features:
            browser_args.append(f"--disable-blink-features={','.join(blink_features)}")

        # Chrome logging
        if merged.get("enable_logging"):
            browser_args.append(f"--log-level={merged.get('log_level', 0)}")
            browser_args.append("--enable-logging")

        # Chrome args from config (user-defined only)
        for arg in browser_cfg.chrome_args or []:
            if arg not in browser_args:
                browser_args.append(arg)

        # Extra user-supplied arguments
        for arg in merged.get("arguments") or []:
            if arg not in browser_args:
                browser_args.append(arg)

        # ── Headless ─────────────────────────────────────────────────
        headless = merged.get("headless") if merged.get("headless") is not None else browser_cfg.headless

        # ── User data dir ────────────────────────────────────────────
        user_data_dir = merged.get("user_data_dir") or browser_cfg.user_data_dir
        if user_data_dir:
            os.makedirs(user_data_dir, exist_ok=True)

        # ── Binary location ──────────────────────────────────────────
        binary_location = merged.get("binary_location")

        # ── Create the browser via nodriver ──────────────────────────
        try:
            config = uc.Config()
            config.headless = headless or False

            # nodriver's add_argument rejects args it manages via attributes
            # (headless, data-dir, no-sandbox, lang), so we handle those
            # through Config attributes and only add the rest.
            _managed = ("headless", "data-dir", "data_dir", "no-sandbox", "no_sandbox", "lang")
            for arg in browser_args:
                if any(m in arg.lower() for m in _managed):
                    # --no-sandbox → config.sandbox = False
                    if "no-sandbox" in arg.lower() or "no_sandbox" in arg.lower():
                        config.sandbox = False
                    continue
                config.add_argument(arg)

            if user_data_dir:
                config.user_data_dir = user_data_dir

            # nodriver has no profile_directory attribute, so we pass it
            # as a Chrome argument.  This ensures all runs share the same
            # Chrome profile (cookies, sessions, local-storage, etc.).
            profile_dir = merged.get("profile_directory") or browser_cfg.profile_directory
            if profile_dir:
                config.add_argument(f"--profile-directory={profile_dir}")

            if binary_location:
                config.browser_executable_path = binary_location

            self.browser = await uc.start(config)
        except Exception as exc:
            self.logger.error(f"Failed to create browser: {exc}")
            raise

        # Navigate to the initial URL
        try:
            self.tab = await self.browser.get(url)
            # Set window size after tab is available
            try:
                await self.tab.set_window_size(w, h)
            except Exception:
                pass  # Some environments don't support this
            self.logger.info(f"Browser started – navigated to {url}")
        except Exception as exc:
            self.logger.error(f"Failed to navigate to {url}: {exc}")
            raise

        # ── Set user-agent override if specified ─────────────────────
        user_agent = merged.get("user_agent") or (scraping_cfg.user_agent if scraping_cfg else None)
        if user_agent:
            try:
                import nodriver.cdp.network as net
                await self.tab.send(net.set_user_agent_override(user_agent=user_agent))
            except Exception as exc:
                self.logger.warning(f"Could not set user agent: {exc}")

        # ── Always enable CDP / NetworkMonitor ───────────────────────
        await self._enable_network_monitoring(network_cfg)

        return self.tab

    # Alias for backward compatibility
    async def start_driver(self, url: str = "https://www.tiktok.com/", **overrides: Any) -> uc.Tab:
        """Backward-compatible alias for ``start_browser``."""
        return await self.start_browser(url=url, **overrides)

    # ------------------------------------------------------------------ #
    #  Network monitoring                                                  #
    # ------------------------------------------------------------------ #

    async def _enable_network_monitoring(self, network_cfg: NetworkConfig) -> None:
        """Activate CDP and attach a ``NetworkMonitor`` to the tab."""
        if self.tab is None:
            return

        try:
            import nodriver.cdp.network as net
            import nodriver.cdp.runtime as runtime

            await self.tab.send(net.enable(
                max_total_buffer_size=network_cfg.max_buffer_size,
                max_resource_buffer_size=network_cfg.max_resource_buffer,
            ))
            await self.tab.send(runtime.enable())
            self.logger.debug("CDP network monitoring enabled")
        except Exception as exc:
            self.logger.warning(f"Could not enable CDP: {exc}")

        try:
            self.network_monitor = NetworkMonitor(
                tab=self.tab,
                config=self._base_config,
                rate_limiter=self.rate_limiter,
            )
            await self.network_monitor.enable_monitoring()
            self.logger.debug("NetworkMonitor attached and active")
        except Exception as exc:
            self.logger.warning(f"NetworkMonitor could not be initialised: {exc}")
            self.network_monitor = None

    # ------------------------------------------------------------------ #
    #  Teardown                                                            #
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        """Stop the browser and release all resources."""
        if self.browser is not None:
            try:
                self.browser.stop()
                self.logger.info("Browser closed successfully")
            except Exception as exc:
                self.logger.warning(f"Error closing browser: {exc}")
            finally:
                self.browser = None
                self.tab = None
                self.network_monitor = None

    # ------------------------------------------------------------------ #
    #  Context-manager protocol (async)                                    #
    # ------------------------------------------------------------------ #

    async def __aenter__(self) -> "TTScraper":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        # Best-effort cleanup if the user forgets to call close()
        if getattr(self, "browser", None) is not None:
            try:
                self.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    #  Convenience helpers                                                 #
    # ------------------------------------------------------------------ #

    def get_tab(self) -> Optional[uc.Tab]:
        """Return the live Tab instance, or ``None`` if not started."""
        return self.tab

    # Keep backward-compat alias
    def get_driver(self) -> Optional[uc.Tab]:
        """Return the live Tab instance, or ``None`` if not started."""
        return self.tab

    def get_browser(self) -> Optional[uc.Browser]:
        """Return the ``Browser`` instance, or ``None``."""
        return self.browser

    def get_network_monitor(self) -> Optional[NetworkMonitor]:
        """Return the ``NetworkMonitor``, or ``None``."""
        return self.network_monitor

    def get_rate_limiter(self) -> RateLimiter:
        """Return the ``RateLimiter`` instance."""
        return self.rate_limiter

    def __repr__(self) -> str:
        status = "running" if self.browser else "stopped"
        return f"<TTScraper status={status}>"
