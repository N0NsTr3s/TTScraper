from __future__ import annotations
from typing import TYPE_CHECKING, ClassVar, Iterator, Optional
from datetime import datetime
import json

if TYPE_CHECKING:
    from .tiktok import TikTokApi
    from .user import User
    from .video import Video


class Comment:
    """
    A TikTok Comment class using Selenium

    Example Usage
    ```py
    # Comments are typically obtained from videos
    for comment in video.comments():
        logger.info(comment.text)
    ```
    """

    parent: ClassVar[TikTokApi]

    id: Optional[str]
    """TikTok's ID of the Comment"""
    text: Optional[str]
    """The text content of the Comment"""
    create_time: Optional[datetime]
    """The creation time of the Comment"""
    author: Optional[User]
    """The User who created the Comment"""
    like_count: Optional[int]
    """The number of likes on the Comment"""
    reply_comment_total: Optional[int]
    """The number of replies to this Comment"""
    video_id: Optional[str]
    """The ID of the video this comment belongs to"""
    as_dict: dict
    """The raw data associated with this Comment."""

    def __init__(
        self,
        id: Optional[str] = None,
        data: Optional[dict] = None,
        **kwargs,
    ):
        """
        Comments are typically created from video.comments() method.
        """
        self.id = id
        
        if data is not None:
            self.as_dict = data
            self.__extract_from_data()
        
        if not self.id and not data:
            raise TypeError("You must provide id or data parameter.")

    def __extract_from_data(self) -> None:
        """Extract comment information from raw data."""
        if not self.as_dict:
            return
            
        data = self.as_dict
        
        # Extract basic info
        self.id = data.get("cid") or data.get("id") or self.id
        self.text = data.get("text")
        
        # Extract creation time
        timestamp = data.get("create_time") or data.get("createTime")
        if timestamp:
            try:
                timestamp = int(timestamp)
                self.create_time = datetime.fromtimestamp(timestamp)
            except (ValueError, TypeError):
                self.create_time = None
        
        # Extract stats
        self.like_count = data.get("digg_count", 0)
        self.reply_comment_total = data.get("reply_comment_total", 0)
        
        # Extract video ID
        self.video_id = data.get("aweme_id")
        
        # Extract author info
        author_data = data.get("user", {})
        if author_data and hasattr(self, 'parent'):
            self.author = self.parent.user(data=author_data)
        else:
            self.author = author_data

    def replies(self, count: int = 20, cursor: int = 0, **kwargs) -> Iterator[Comment]:
        """
        Returns the replies to this comment.

        Parameters:
            count (int): The amount of replies you want returned.
            cursor (int): The offset of replies from 0 you want to get.

        Returns:
            iterator/generator: Yields Comment objects.

        Example Usage
        .. code-block:: python

            for reply in comment.replies():
                logger.info(reply.text)
        """
        found = 0
        while found < count:
            params = {
                "item_id": self.video_id,
                "comment_id": self.id,
                "count": 20,
                "cursor": cursor,
            }

            if hasattr(self, 'parent') and hasattr(self.parent, 'make_request'):
                resp = self.parent.make_request(
                    url="https://www.tiktok.com/api/comment/list/reply/",
                    params=params,
                    headers=kwargs.get("headers"),
                    session_index=kwargs.get("session_index"),
                )

                if resp is None:
                    from .video import InvalidResponseException
                    raise InvalidResponseException(
                        resp, "TikTok returned an invalid response."
                    )

                for reply_data in resp.get("comments", []):
                    yield self.parent.comment(data=reply_data)
                    found += 1

                if not resp.get("has_more", False):
                    return

                cursor = int(resp.get("cursor") or 0)
            else:
                break

    def get_summary(self) -> dict:
        """Get a summary of the comment information."""
        author_name = None
        if self.author:
            if hasattr(self.author, 'username'):
                author_name = self.author.username
            elif isinstance(self.author, dict):
                author_name = self.author.get('uniqueId') or self.author.get('nickname')
        
        return {
            'id': self.id,
            'text': self.text[:100] + '...' if self.text and len(self.text) > 100 else self.text,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'author': author_name,
            'like_count': self.like_count,
            'reply_count': self.reply_comment_total,
            'video_id': self.video_id,
            'has_data': bool(self.as_dict)
        }


    def __repr__(self):
        return self.__str__()

    def __str__(self):
        preview = self.text[:50] + '...' if self.text and len(self.text) > 50 else self.text
        return f"Comment(id='{getattr(self, 'id', None)}', text='{preview}')"
