from typing import Dict
from uuid import UUID

from utils.constants import BASE_STORAGE_DIRECTORY, IMAGE_ENLARGEMENTS


def check_dir_path_rename(obj_dict: Dict, dir_path: str, new_dir_name: str, company_id: UUID) -> bool:
    """
   Проверки:
   1) В пути кол-во '/' больше 1
   2) В пути последний символ '/'
   3) В названии папки последний символ '/'
   4) Совпадения пути папки компании, где хотят положить файл, с путем компании, на которую выданы права доступа
   5) Наличия такого пути в S3Storage
   6) Отсутствие директории с новым названием
   :return: возможность загрузки файла
   """
    if dir_path.count('/') < 2 or dir_path[-1] != '/' or new_dir_name[-1] != '/':
        return False
    real_dir_path = BASE_STORAGE_DIRECTORY.COMPANY + "company_{0}".format(str(company_id))
    request_dir_path = dir_path[:dir_path.index('/', dir_path.index('/') + 1)]
    if real_dir_path != request_dir_path:
        return False
    return dir_path in obj_dict.keys() and dir_path + new_dir_name not in obj_dict.keys()
