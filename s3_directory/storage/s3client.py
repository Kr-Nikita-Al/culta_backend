from contextlib import asynccontextmanager
from typing import Dict
from uuid import UUID

from aiobotocore.session import get_session
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import NoCredentialsError, ClientError
from fastapi import HTTPException

from s3_directory.actions import check_file_path_put, check_size_limits, check_file_path_get
from utils.constants import CONFIG_S3CLIENT, BASE_STORAGE_DIRECTORY, EMPTY_UUID


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

    async def update_file_place_object(self, old_file_path: str, new_file_path: str,
                                       old_file_name: str, new_file_name: str, company_id: UUID):
        """
        Метод обновления расположения и имени файла
        :return: url
        """
        try:
            async with self.__get_client() as client:
                obj_dict = await self.get_all_objects()
                if not check_file_path_get(file_path=old_file_path, obj_dict=obj_dict, company_id=company_id):
                    raise HTTPException(status_code=422, detail='Incorrect old file name')
                if not check_file_path_put(file_path=new_file_path, obj_dict=obj_dict, file_name=new_file_name,
                                           company_id=company_id):
                    raise HTTPException(status_code=422, detail='Incorrect file path or new file name')
                # 1. Копируем объект с новым именем
                copy_response = await client.copy_object(Bucket=self.bucket_name, Key=new_file_path + new_file_name,
                                                         CopySource={'Bucket': self.bucket_name,
                                                                     'Key': old_file_path + old_file_name})
                # 2. Проверяем успешность копирования и удаляем исходный файл
                if copy_response['ResponseMetadata']['HTTPStatusCode'] != 200:
                    raise HTTPException(status_code=404, detail="Renamed file not found")
                _ = await client.delete_object(Bucket=self.bucket_name, Key=old_file_path + old_file_name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File not found")
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="Keys not found")
        except (ClientError, S3UploadFailedError) as e:
            raise HTTPException(status_code=422, detail=f"Error: {e.response['Error']['Message']}")

    async def delete_object(self, file_path: str, file_name: str, company_id: UUID):
        """
        Метод удаления файла по путям file_path
        :return: url
        """
        try:
            async with self.__get_client() as client:
                obj_dict = await self.get_all_objects()
                if not check_file_path_get(file_path=file_path, obj_dict=obj_dict, company_id=company_id):
                    raise HTTPException(status_code=422, detail='Incorrect file path')
                _ = await client.delete_object(Bucket=self.bucket_name, Key=file_path + file_name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File not found")
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="Keys not found")
        except (ClientError, S3UploadFailedError) as e:
            raise HTTPException(status_code=422, detail=f"Error: {e.response['Error']['Message']}")

    async def generate_get_presigned_url(self, file_path: str, file_name: str, company_id: UUID = EMPTY_UUID) -> str:
        """
        Метод динамической генерации преподписанного урла для скачивания файла
        :return: url
        """
        try:
            async with self.__get_client() as client:
                obj_dict = await self.get_all_objects()
                if not check_file_path_get(file_path=file_path, obj_dict=obj_dict, company_id=company_id):
                    raise HTTPException(status_code=422, detail='Incorrect file path')
                url = await client.generate_presigned_url(ClientMethod='get_object', ExpiresIn=120,
                                                          Params={'Bucket': self.bucket_name,
                                                                  'Key': file_path + file_name})
                return url
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File not found")
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="Keys not found")
        except (ClientError, S3UploadFailedError) as e:
            raise HTTPException(status_code=422, detail=f"Error: {e.response['Error']['Message']}")

    async def generate_put_presigned_url(self, file_path: str, file_name: str, file_size: float, company_id: UUID) -> str:
        """
        Метод динамической генерации преподписанного урла для загрузки файла
        :param file_path: путь до файла
        :param file_name: название файла
        :param file_size: размер файла
        :param company_id: id компании, где есть права для размещения изображения
        :return: url
        """
        try:
            obj_dict = await self.get_objects_by_dir_name(dir_name=file_path)
            if not check_file_path_put(file_path=file_path, obj_dict=obj_dict, file_name=file_name,
                                       company_id=company_id):
                raise HTTPException(status_code=422, detail='Incorrect file path or file name')
            if not check_size_limits(obj_dict=obj_dict, file_size=file_size):
                raise HTTPException(status_code=422, detail='Incorrect file size')
            async with self.__get_client() as client:
                url = await client.generate_presigned_url(ClientMethod='put_object', ExpiresIn=120,
                                                          Params={'Bucket': self.bucket_name,
                                                                  'Key': file_path + file_name})
                return url
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="Keys not found")
        except (ClientError, S3UploadFailedError) as e:
            raise HTTPException(status_code=422, detail=f"Error: {e.response['Error']['Message']}")

    async def create_directory(self, dir_name: str, dir_path: str):
        """
        Метод создания директории в S3Storage
        :param dir_name: название новой директории
        :param dir_path: путь, где необходимо создать директорию
        :return:
        """
        if BASE_STORAGE_DIRECTORY.USER not in dir_path and BASE_STORAGE_DIRECTORY.COMPANY not in dir_path:
            raise HTTPException(status_code=422, detail='Incorrect path')
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
            raise HTTPException(status_code=403, detail="Keys not found")
        except (ClientError, S3UploadFailedError) as e:
            raise HTTPException(status_code=422, detail=f"Error: {e.response['Error']['Message']}")
