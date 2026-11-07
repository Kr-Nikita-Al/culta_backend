from uuid import uuid4
import pytest
from pydantic import ValidationError
from company.interface_request import UpdateCompanyRequest
from product_card.interface_request import UpdateProductCardRequest
from image.interface_request.update_image_request import UpdateImageRequest
from navigations.screen.interface_request import UpdateScreenRequest
from navigations.container.interface_request import UpdateContainerRequest
from navigations.item.interface_request import UpdateItemRequest


@pytest.mark.parametrize('model', [UpdateCompanyRequest, UpdateProductCardRequest, UpdateImageRequest,
                                  UpdateScreenRequest, UpdateContainerRequest, UpdateItemRequest])
def test_immutable_company_id_is_rejected_not_silently_ignored(model):
    with pytest.raises(ValidationError):
        model(company_id=str(uuid4()))


@pytest.mark.parametrize('model,field', [(UpdateCompanyRequest,'basic_screen_id'),
    (UpdateCompanyRequest,'image_picture_id'), (UpdateCompanyRequest,'image_icon_id'),
    (UpdateProductCardRequest,'image_product_id'), (UpdateProductCardRequest,'image_icon_id'),
    (UpdateImageRequest,'company_group_id')])
def test_uuid_format_and_null_compatibility(model,field):
    with pytest.raises(ValidationError):
        model(**{field:'invalid'})
    assert model(**{field:None}).dict(exclude_none=True) == {}
    uid = uuid4()
    assert getattr(model(**{field:str(uid)}),field) == uid
