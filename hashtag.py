from __future__ import annotations
from typing import TYPE_CHECKING, ClassVar, Iterator, Optional
import json

if TYPE_CHECKING:
    from .tiktok import TikTokApi


class Hashtag:
    """
    A TikTok Hashtag class using Selenium

    Example Usage
    ```py
    hashtag = api.hashtag(name='fyp')
    ```
    """

    parent: ClassVar[TikTokApi]

    id: Optional[str]
    """TikTok's ID of the Hashtag"""
    name: Optional[str]
    """The name of the Hashtag"""
    title: Optional[str]
    """The title of the Hashtag"""
    description: Optional[str]
    """The description of the Hashtag"""
    video_count: Optional[int]
    """The number of videos using this Hashtag"""
    view_count: Optional[int]
    """The number of views for this Hashtag"""
    is_commerce: Optional[bool]
    """Whether this is a commerce hashtag"""
    as_dict: dict
    """The raw data associated with this Hashtag."""

    def __init__(
        self,
        name: Optional[str] = None,
        id: Optional[str] = None,
        data: Optional[dict] = None,
        **kwargs,
    ):
        """
        You must provide the name, id, or data, else this will fail.
        """
        self.name = name
        self.id = id
        
        if data is not None:
            self.as_dict = data
            self.__extract_from_data()
        
        if not any([self.name, self.id, data]):
            raise TypeError("You must provide name, id, or data parameter.")

    def __extract_from_data(self) -> None:
        """Extract hashtag information from raw data."""
        if not self.as_dict:
            return
            
        data = self.as_dict
        
        # Extract basic info
        self.id = data.get("id") or self.id
        self.name = data.get("title") or data.get("name") or self.name
        self.title = data.get("title")
        self.description = data.get("desc") or data.get("description")
        
        # Extract stats
        stats = data.get("stats", {})
        self.video_count = stats.get("videoCount", 0)
        self.view_count = stats.get("viewCount", 0)
        
        # Extract other properties
        self.is_commerce = data.get("isCommerce", False)

    def videos(self, count: int = 30, cursor: int = 0, **kwargs) -> Iterator:
        """
        Returns videos that use this hashtag.

        Parameters:
            count (int): The amount of videos you want returned.
            cursor (int): The offset of videos from 0 you want to get.

        Returns:
            iterator/generator: Yields Video objects.

        Example Usage
        .. code-block:: python

            for video in hashtag.videos():
                # do something
        """
        found = 0
        while found < count:
            params = {
                "challengeID": self.id,
                "count": 30,
                "cursor": cursor,
            }

            if hasattr(self, 'parent') and hasattr(self.parent, 'make_request'):
                resp = self.parent.make_request(
                    url="https://www.tiktok.com/api/challenge/item_list/",
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
        """Get a summary of the hashtag information."""
        return {
            'id': self.id,
            'name': self.name,
            'title': self.title,
            'description': self.description,
            'video_count': self.video_count,
            'view_count': self.view_count,
            'is_commerce': self.is_commerce,
            'has_data': bool(self.as_dict)
        }

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"Hashtag(name='{getattr(self, 'name', None)}')"
