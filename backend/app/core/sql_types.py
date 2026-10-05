"""Portable UUID binding; accept both canonical strings and UUID objects."""

import uuid

import sqlalchemy as sa
from sqlalchemy.engine import Dialect


class UUID(sa.TypeDecorator[uuid.UUID | str]):
    impl = sa.Uuid
    cache_ok = True

    def __init__(self, as_uuid: bool = True):
        super().__init__(as_uuid=as_uuid)
        self.as_uuid = as_uuid

    def process_bind_param(self, value: uuid.UUID | str | None, dialect: Dialect) -> uuid.UUID | str | None:
        if value is None:
            return None
        parsed = uuid.UUID(str(value))
        return parsed if self.as_uuid else str(parsed)
