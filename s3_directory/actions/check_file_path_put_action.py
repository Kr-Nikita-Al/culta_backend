from typing import Dict
from uuid import UUID

from utils.constants import BASE_STORAGE_DIRECTORY, IMAGE_ENLARGEMENTS


def check_file_path_put(obj_dict: Dict, file_path: str, file_name: str, company_id: UUID) -> bool:
    """
   Проверки:
   1) В пути кол-во '/' больше 1
   2) В пути последний символ '/'
   3) В названии файла есть '.'
   4) Совпадения пути папки компании, где хотят положить файл, с путем компании, на которую выданы права доступа
   5) Корректность расширения файла
   6) Наличия такого пути в S3Storage
   7) Отсутствие файла с таким названием
   :return: возможность загрузки файла
   """
    if file_path.count('/') < 2 or file_path[-1] != '/' or file_name.count('.') < 1:
        return False
    real_dir_path = BASE_STORAGE_DIRECTORY.COMPANY + "company_{0}".format(str(company_id))
    request_dir_path = file_path[:file_path.index('/', file_path.index('/') + 1)]
    if real_dir_path != request_dir_path:
        return False
    enlargement = file_name.split('.')[1]
    return file_path in obj_dict.keys() and \
        enlargement in IMAGE_ENLARGEMENTS and \
        file_path + file_name not in obj_dict.keys()
