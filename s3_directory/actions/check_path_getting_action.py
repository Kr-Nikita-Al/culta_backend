from typing import Dict
from uuid import UUID

from utils.constants import BASE_STORAGE_DIRECTORY, EMPTY_UUID


def check_path_getting(obj_dict: Dict, obj_path: str, company_id: UUID) -> bool:
    """
   Проверки (1) только по необходимости):
   1) Совпадения пути папки компании, откуда хотят получить объект, с путем компании, на которую выданы права доступа
   2) Наличия пути до объекта (папка или изображение) в S3Storage
   :return: возможность выгрузить файл
   """
    if company_id != EMPTY_UUID:
        real_dir_path = BASE_STORAGE_DIRECTORY.COMPANY + "company_{0}".format(str(company_id))
        request_dir_path = obj_path[:obj_path.index('/', obj_path.index('/') + 1)]
        return real_dir_path == request_dir_path and obj_path in obj_dict.keys()
    return obj_path in obj_dict.keys()
