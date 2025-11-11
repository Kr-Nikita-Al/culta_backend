from typing import Dict

from utils.constants import QUOTA_FILE_SIZE, QUOTA_STORAGE_SIZE


def check_size_limits(obj_dict: Dict, file_size: float) -> bool:
    """
    Проверка на лимит по размеру файла, размеру существующих файлов в папке, кол-ву файлов
    :return:
    """
    if file_size > QUOTA_FILE_SIZE or file_size <= 0:
        return False
    dir_size = sum(list(obj_dict.values())) + file_size
    if dir_size > QUOTA_STORAGE_SIZE:
        return False
    return True
