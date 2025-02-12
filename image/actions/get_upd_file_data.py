from typing import Dict

from image.interface_response import GetImageInterface


def __get_upd_file_data(upd_image_params: Dict, upd_image: GetImageInterface) -> Dict:
    dict_file_data = {}
    if 'file_name' in upd_image_params or 'file_path' in upd_image_params:
        dict_file_data['file_path'] = upd_image_params['file_path'] if 'file_path' in upd_image_params else upd_image.file_path
        dict_file_data['file_name'] = upd_image_params['file_name'] if 'file_name' in upd_image_params else upd_image.file_name
    return dict_file_data
