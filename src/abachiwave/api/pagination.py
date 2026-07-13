from typing import Annotated

from fastapi import Depends, Query

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


class PageParams:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


PageDependency = Annotated[PageParams, Depends()]
