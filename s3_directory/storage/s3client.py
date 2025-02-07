from contextlib import asynccontextmanager
from typing import Dict

from aiobotocore.session import get_session
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import NoCredentialsError, ClientError
from fastapi import HTTPException

from utils.constants import CONFIG_S3CLIENT, LIMIT_FILE_SIZE, LIMIT_DIRECTORY_SIZE, \
                            IMAGE_ENLARGEMENTS, BASE_STORAGE_DIRECTORY


class S3Client:

    def __init__(self, bucket_name: str = 'culta-images'):
        self.bucket_name = bucket_name
        self.session = get_session()

    @asynccontextmanager
    async def __get_client(self):
        async with self.session.create_client('s3', **CONFIG_S3CLIENT) as client:
            yield client

    async def get_all_objects(self) -> Dict:
        """
        Метод получения списка файлов во всех директориях S3Storage
        :return: словарь типа {путь до файла: размер в байтах}
        """
        try:
            async with self.__get_client() as client:
                response = await client.list_objects_v2(Bucket=self.bucket_name)
                return {obj['Key']: obj['Size'] for obj in response.get('Contents', [])}
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="Keys not found")
        except (ClientError, S3UploadFailedError) as e:
            raise HTTPException(status_code=422, detail=f"Error: {e.response['Error']['Message']}")

    async def get_objects_by_dir_name(self, dir_name: str) -> Dict:
        """
        Метод получения списка файлов в папке пользователя или компании
        :return: словарь типа {путь до файла: размер в байтах}
        """
        obj_dict = await self.get_all_objects()
        return {k: v for k, v in obj_dict.items() if dir_name in k}

    async def check_size_limits(self, dir_name: str, file_size: float) -> bool:
        """
        Проверка на лимит по размеру файла, размеру существующих файлов в папке, кол-ву файлов
        :return:
        """
        if file_size > LIMIT_FILE_SIZE:
            return False
        obj_dict = await self.get_objects_by_dir_name(dir_name=dir_name)
        dir_size = sum(list(obj_dict.values())) + file_size
        if dir_size > LIMIT_DIRECTORY_SIZE:
            return False
        return True

    async def check_file_path(self, file_path: str) -> bool:
        """
       Проверка на корректность расширения файла и наличия директории в S3Storage
       :return: возможность загрузки файла
       """
        if BASE_STORAGE_DIRECTORY.USER not in file_path and BASE_STORAGE_DIRECTORY.COMPANY not in file_path:
            return False
        enlargement = file_path.split('.')[1]
        path_to_dir = file_path[:file_path.rfind('/')+1]
        obj_dict = await self.get_all_objects()
        return path_to_dir in obj_dict.keys() and enlargement in IMAGE_ENLARGEMENTS

    async def generate_get_presigned_url(self, full_file_path: str) -> str:
        """
        Метод динамической генерации урла для скачивания/загрузки файла
        :return: url
        """
        try:
            async with self.__get_client() as client:
                obj_dict = await self.get_all_objects()
                if full_file_path not in obj_dict.keys():
                    raise HTTPException(status_code=422, detail='Incorrect file path')
                url = await client.generate_presigned_url(ClientMethod='get_object', ExpiresIn=120,
                                                          Params={'Bucket': self.bucket_name, 'Key': full_file_path})
                return url
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File not found")
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="Ключи доступа не найдены.")
        except (ClientError, S3UploadFailedError) as e:
            raise HTTPException(status_code=422, detail=f"Ошибка: {e.response['Error']['Message']}")

    async def generate_put_presigned_url(self, full_file_path: str, file_size: float) -> str:
        """
        Метод динамической генерации урла для скачивания/загрузки файла
        :return: url
        """
        try:
            async with self.__get_client() as client:
                if not await self.check_file_path(file_path=full_file_path):
                    raise HTTPException(status_code=422, detail='Incorrect file path')
                if not await self.check_size_limits(dir_name=full_file_path.split('/')[1], file_size=file_size):
                    raise HTTPException(status_code=422, detail='Incorrect file size')
                url = await client.generate_presigned_url(ClientMethod='put_object', ExpiresIn=120,
                                                          Params={'Bucket': self.bucket_name, 'Key': full_file_path})
                return url
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="Ключи доступа не найдены.")
        except (ClientError, S3UploadFailedError) as e:
            raise HTTPException(status_code=422, detail=f"Ошибка: {e.response['Error']['Message']}")

    async def create_directory(self, dir_name: str, dir_path: str):
        """
        Метод создания директории в S3Storage
        :param dir_name: название новой директории
        :param dir_path: путь, где необходимо создать директорию
        :return:
        """
        if BASE_STORAGE_DIRECTORY.USER not in dir_path and BASE_STORAGE_DIRECTORY.COMPANY not in dir_path:
            raise HTTPException(status_code=422, detail='Incorrect path')
        dir_path = dir_path + '/' if dir_path[-1] != '/' else dir_path
        try:
            async with self.__get_client() as client:
                obj_dict = await self.get_all_objects()
                # Check company was not created early
                if dir_path + dir_name + '/' not in obj_dict.keys():
                    await client.put_object(Bucket=self.bucket_name, Key=f"{dir_path + dir_name}/")
                else:
                    raise HTTPException(status_code=409,
                                        detail='Directory with name <{0}> already exist in storage'.format(dir_name))
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="Ключи доступа не найдены.")
        except (ClientError, S3UploadFailedError) as e:
            raise HTTPException(status_code=422, detail=f"Ошибка: {e.response['Error']['Message']}")


# async def main():
#     s3client = S3Client()
#     # url = await s3client.generate_presigned_url(filename='company_0101/image.jpg', file_size=100)
#     # print("Подписная ссылка:", url)
#
#     # await s3client.create_company_directory('company_0101')
#
#     d = await s3client.get_objects_by_dir_name('company_8419cbac-c063-44f4-b8c6-61f3263a20ee')
#     print(d)
#
#
# asyncio.run(main())
