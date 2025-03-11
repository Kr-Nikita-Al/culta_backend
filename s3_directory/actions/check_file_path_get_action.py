from typing import Dict
from uuid import UUID

from utils.constants import BASE_STORAGE_DIRECTORY, EMPTY_UUID


def check_file_path_get(obj_dict: Dict, file_path: str, company_id: UUID) -> bool:
    """
   Проверки (1) только по необходимости):
   1) Совпадения пути папки компании, откуда хотят выгрузить файл, с путем компании, на которую выданы права доступа
   2) Наличия такого пути в S3Storage
   :return: возможность выгрузить файл
   """
    if company_id != EMPTY_UUID:
        real_dir_path = BASE_STORAGE_DIRECTORY.COMPANY + "company_{0}".format(str(company_id))
        request_dir_path = file_path[:file_path.index('/', file_path.index('/') + 1)]
        return real_dir_path == request_dir_path and file_path in obj_dict.keys()
    return file_path in obj_dict.keys()
