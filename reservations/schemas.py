from datetime import datetime, timedelta
from typing import List, Literal, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, conint, constr, conlist, root_validator, validator
from utils.base_model_response import BaseModelResponse


class StrictRequest(BaseModel):
    class Config:
        extra = 'forbid'


class Table(StrictRequest):
    table_id: UUID
    label: constr(strip_whitespace=True, min_length=1, max_length=40)
    shape: Literal['square', 'rectangle', 'circle']
    seats: conint(strict=True, ge=1, le=24)
    x: conint(strict=True, ge=0, le=4000)
    y: conint(strict=True, ge=0, le=2400)
    width: conint(strict=True, ge=50, le=220)
    height: conint(strict=True, ge=50, le=220)

    @root_validator(skip_on_failure=True)
    def geometry(cls, v):
        if v['shape'] != 'rectangle' and v['width'] != v['height']:
            raise ValueError('Circle and square must have equal width and height')
        if not (v['width']/2+20 <= v['x'] <= 3980-v['width']/2 and
                v['height']/2+20 <= v['y'] <= 2380-v['height']/2):
            raise ValueError('Table and chairs must stay inside the floor plan')
        return v

    class Config(StrictRequest.Config):
        orm_mode = True


class Room(StrictRequest):
    room_id: UUID
    label: constr(strip_whitespace=True, min_length=1, max_length=40)
    x: conint(strict=True, ge=0, le=4000)
    y: conint(strict=True, ge=0, le=2400)
    width: conint(strict=True, ge=100, le=4000)
    height: conint(strict=True, ge=80, le=2400)

    @root_validator(skip_on_failure=True)
    def geometry(cls, v):
        if v['x'] + v['width'] > 4000 or v['y'] + v['height'] > 2400:
            raise ValueError('Room must stay inside the floor plan')
        return v


class LayoutRequest(StrictRequest):
    company_id: UUID
    version: conint(strict=True, ge=0)
    width: Optional[conint(strict=True, ge=300, le=4000)] = None
    height: Optional[conint(strict=True, ge=200, le=2400)] = None
    tables: conlist(Table, max_items=80)
    # Older clients may omit rooms; this must not erase them.
    rooms: Optional[conlist(Room, max_items=30)] = None

    @validator('rooms')
    def unique_rooms(cls, rooms):
        if rooms is not None and (len({r.room_id for r in rooms}) != len(rooms) or
                                 len({r.label.casefold() for r in rooms}) != len(rooms)):
            raise ValueError('Room IDs and names must be unique')
        return rooms

    @validator('tables')
    def unique_tables(cls, tables):
        if len({t.table_id for t in tables}) != len(tables) or len({t.label.casefold() for t in tables}) != len(tables):
            raise ValueError('Table IDs and names must be unique')
        return tables


class BookingRequest(StrictRequest):
    company_id: UUID
    table_id: UUID
    request_id: UUID = Field(default_factory=uuid4)
    guests: conint(strict=True, ge=1, le=24)
    starts_at: datetime
    ends_at: datetime
    # Staff can book for an unregistered guest. Clients cannot override identity.
    guest_name: Optional[constr(strip_whitespace=True, min_length=1, max_length=100)] = None
    guest_phone: Optional[constr(strip_whitespace=True, min_length=1, max_length=30)] = None

    @validator('starts_at', 'ends_at')
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Timezone offset is required')
        return value

    @root_validator(skip_on_failure=True)
    def interval(cls, v):
        duration = v['ends_at'] - v['starts_at']
        if not timedelta(minutes=15) <= duration <= timedelta(hours=12):
            raise ValueError('Booking duration must be between 15 minutes and 12 hours')
        return v


class RescheduleRequest(BookingRequest):
    version: conint(strict=True, ge=1)


class StatusRequest(StrictRequest):
    company_id: UUID
    version: conint(strict=True, ge=1)
    status: Literal['seated', 'completed', 'canceled']


class BookingResponse(BaseModelResponse):
    reservation_id: UUID
    table_id: UUID
    company_id: UUID
    user_id: Optional[UUID]
    guest_name: str
    guest_phone: str
    guests: int
    starts_at: datetime
    ends_at: datetime
    status: str
    version: int


class Occupancy(BaseModelResponse):
    table_id: UUID
    starts_at: datetime
    ends_at: datetime
    status: str


class BoardResponse(BaseModelResponse):
    version: int
    width: int = 1000
    height: int = 600
    tables: List[Table]
    rooms: List[Room] = Field(default_factory=list)
    bookings: List[BookingResponse]
    occupancy: List[Occupancy]
    can_edit_plan: bool
    can_manage_bookings: bool
    server_time: datetime
