from __future__ import annotations
from typing import TYPE_CHECKING, ClassVar, Iterator, Optional
import json

if TYPE_CHECKING:
    from .tiktok import TikTokApi


class Sound:
    """
    A TikTok Sound class using Selenium

    Example Usage
    ```py
    sound = api.sound(id='7016547803243022337')
    ```
    """

    parent: ClassVar[TikTokApi]

    id: Optional[str]
    """TikTok's ID of the Sound"""
    title: Optional[str]
    """The title of the Sound"""
    author_name: Optional[str]
    """The author of the Sound"""
    play_url: Optional[str]
    """The URL to play the Sound"""
    duration: Optional[int]
    """The duration of the Sound in seconds"""
    video_count: Optional[int]
    """The number of videos using this Sound"""
    as_dict: dict
    """The raw data associated with this Sound."""

    def __init__(
        self,
        id: Optional[str] = None,
        data: Optional[dict] = None,
        **kwargs,
    ):
        """
        You must provide the id or data, else this will fail.
        """
        self.id = id
        
        if data is not None:
            self.as_dict = data
            self.__extract_from_data()
        
        if not self.id and not data:
            raise TypeError("You must provide id or data parameter.")

    def __extract_from_data(self) -> None:
        """Extract sound information from raw data."""
        if not self.as_dict:
            return
            
        data = self.as_dict
        
        # Handle different data structures
        # Sometimes the sound data is nested under 'music' key
        if 'music' in data:
            sound_data = data['music']
        else:
            sound_data = data
        
        # Extract basic info
        self.id = sound_data.get("id") or self.id
        self.title = sound_data.get("title")
        self.author_name = sound_data.get("authorName")
        self.duration = sound_data.get("duration")
        
        # Extract play URL - try different possible keys
        self.play_url = (
            sound_data.get("playUrl") or 
            sound_data.get("play") or
            sound_data.get("original", {}).get("playUrl") if isinstance(sound_data.get("original"), dict) else None
        )
        
        # Extract video count
        stats = sound_data.get("stats", {})
        self.video_count = stats.get("videoCount", 0)

    def videos(self, count: int = 30, cursor: int = 0, **kwargs) -> Iterator:
        """
        Returns videos that use this sound.

        Parameters:
            count (int): The amount of videos you want returned.
            cursor (int): The offset of videos from 0 you want to get.

        Returns:
            iterator/generator: Yields Video objects.

        Example Usage
        .. code-block:: python

            for video in sound.videos():
                # do something
        """
        found = 0
        while found < count:
            params = {
                "musicID": self.id,
                "count": 30,
                "cursor": cursor,
            }

            if hasattr(self, 'parent') and hasattr(self.parent, 'make_request'):
                resp = self.parent.make_request(
                    url="https://www.tiktok.com/api/music/item_list/",
                    params=params,
                    headers=kwargs.get("headers"),
                    session_index=kwargs.get("session_index"),
                )

                if resp is None:
                    from .video import InvalidResponseException
                    raise InvalidResponseException(
                        resp, "TikTok returned an invalid response."
                    )

                for video_data in resp.get("itemList", []):
                    yield self.parent.video(data=video_data)
                    found += 1

                if not resp.get("hasMore", False):
                    return

                cursor = resp.get("cursor", 0)
                if cursor is None:
                    cursor = 0
            else:
                break

    def get_summary(self) -> dict:
        """Get a summary of the sound information."""
        return {
            'id': self.id,
            'title': self.title,
            'author_name': self.author_name,
            'duration': self.duration,
            'video_count': self.video_count,
            'play_url': self.play_url,
            'has_data': bool(self.as_dict)
        }

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"Sound(id='{getattr(self, 'id', None)}', title='{getattr(self, 'title', None)}')"
