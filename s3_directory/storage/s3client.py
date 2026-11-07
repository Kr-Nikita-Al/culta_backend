from contextlib import asynccontextmanager
import asyncio
from typing import Dict
from uuid import UUID

from aiobotocore.session import get_session
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import NoCredentialsError, ClientError, BotoCoreError
from fastapi import HTTPException, UploadFile

from s3_directory.actions import check_file_path_put, check_size_limits, check_path_getting, check_dir_path_rename
from settings import AWS_BUCKET_NAME
from utils.constants import CONFIG_S3CLIENT, BASE_STORAGE_DIRECTORY, EMPTY_UUID, IMAGE_UPLOAD_URL_TTL_SECONDS, QUOTA_IMAGE_SIZE


class S3Client:

    async def versioning_enabled(self):
        async with self.__get_client() as client:
            result = await client.get_bucket_versioning(Bucket=self.bucket_name)
            return result.get('Status') == 'Enabled'

    async def get_version_metadata(self, key, version_id):
        if not isinstance(version_id, str) or not version_id or version_id == 'null':
            raise HTTPException(422, 'A concrete version is required')
        try:
            async with self.__get_client() as client:
                result = await client.head_object(Bucket=self.bucket_name, Key=key, VersionId=version_id)
                return {'version_id':result.get('VersionId')}
        except ClientError as error:
            if str(error.response.get('Error', {}).get('Code')) in ('404', 'NoSuchKey', 'NoSuchVersion', 'NotFound'):
                return None
            raise HTTPException(503, 'Storage temporarily unavailable') from None

    async def delete_exact_version(self, key, version_id, company_id):
        root = f'{BASE_STORAGE_DIRECTORY.COMPANY}company_{company_id}/'
        if (not key.startswith(root) or '\\' in key or any(p in ('.', '..') for p in key.split('/'))
                or not isinstance(version_id, str) or not version_id or version_id == 'null'):
            raise HTTPException(422, 'Invalid version deletion target')
        async with self.__get_client() as client:
            await client.delete_object(Bucket=self.bucket_name, Key=key, VersionId=version_id)

    async def download_image(self, file_path: str, file_name: str, company_id: UUID) -> bytes:
        """Read a tenant key through configured storage, never a caller-supplied URL."""
        root = f'{BASE_STORAGE_DIRECTORY.COMPANY}company_{company_id}/'
        if (not file_path.startswith(root) or not file_path.endswith('/')
                or not file_name or '/' in file_name or '\\' in file_name
                or any(part in ('.', '..') for part in (file_path + file_name).split('/'))):
            raise HTTPException(422, 'Incorrect file path')
        try:
            async with asyncio.timeout(30):
                async with self.__get_client() as client:
                    result = await client.get_object(Bucket=self.bucket_name, Key=file_path + file_name)
                    async with result['Body'] as stream:
                        if result.get('ContentLength', 0) > QUOTA_IMAGE_SIZE:
                            raise HTTPException(413, 'Image too large')
                        data = bytearray()
                        while True:
                            chunk = await stream.read(min(65536, QUOTA_IMAGE_SIZE + 1 - len(data)))
                            if not chunk:
                                return bytes(data)
                            data.extend(chunk)
                            if len(data) > QUOTA_IMAGE_SIZE:
                                raise HTTPException(413, 'Image too large')
        except ClientError as error:
            if error.response.get('Error', {}).get('Code') in ('404', 'NoSuchKey', 'NotFound'):
                raise HTTPException(404, 'Image not found') from None
            raise HTTPException(503, 'Storage temporarily unavailable') from None
        except (BotoCoreError, TimeoutError):
            raise HTTPException(503, 'Storage temporarily unavailable') from None

    def __init__(self, bucket_name: str = AWS_BUCKET_NAME):
        self.bucket_name = bucket_name
        self.session = get_session()

    @asynccontextmanager
    async def __get_client(self):
        async with self.session.create_client('s3', **CONFIG_S3CLIENT) as client:
            yield client

    async def get_all_objects(self, prefix: str = '') -> Dict:
        """
        Метод получения списка файлов во всех директориях S3Storage
        :return: словарь типа {путь до файла: размер в байтах}
        """
        try:
            async with self.__get_client() as client:
                objects = {}
                paginator = client.get_paginator('list_objects_v2')
                async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                    objects.update({obj['Key']: obj['Size'] for obj in page.get('Contents', [])})
                return objects
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="Keys not found")
        except (ClientError, S3UploadFailedError) as e:
            raise HTTPException(status_code=422, detail=f"Error: {e.response['Error']['Message']}")

    async def get_objects_by_dir_name(self, dir_name: str) -> Dict:
        """
        Метод получения списка файлов в папке пользователя или компании
        :return: словарь типа {путь до файла: размер в байтах}
        """
        if not dir_name:
            raise HTTPException(422, 'Directory is required')
        prefix = dir_name.rstrip('/') + '/'
        return await self.get_all_objects(prefix=prefix)

    async def get_object_metadata(self, key: str) -> Dict:
        """Exact lookup: no bucket-wide listing to retrieve a single image."""
        try:
            async with self.__get_client() as client:
                metadata = await client.head_object(Bucket=self.bucket_name, Key=key)
                return {key: metadata['ContentLength']}
        except NoCredentialsError:
            raise HTTPException(403, 'Keys not found')
        except ClientError as exc:
            if str(exc.response.get('Error', {}).get('Code')) in ('404', 'NoSuchKey', 'NotFound'):
                return {}
            raise HTTPException(503, 'Storage temporarily unavailable')

    async def update_file_place_object(self, old_file_path: str, new_file_path: str,
                                       file_name: str, company_id: UUID, before_copy=None):
        """
        Метод обновления расположения файла
        :return: url
        """
        root = f'{BASE_STORAGE_DIRECTORY.COMPANY}company_{company_id}/'
        if (not file_name or '/' in file_name or '\\' in file_name
                or any(not path.startswith(root) or not path.endswith('/')
                       or any(part in ('.', '..') for part in path.split('/'))
                       for path in (old_file_path, new_file_path))):
            raise HTTPException(422, 'Incorrect file path')
        # Copying an object onto itself and then deleting the source loses it.
        if old_file_path == new_file_path:
            return
        obj_dict = await self.get_objects_by_dir_name(root)
        if not check_path_getting(obj_path=old_file_path + file_name, obj_dict=obj_dict, company_id=company_id):
            raise HTTPException(status_code=422, detail='Incorrect old file name')
        if not check_file_path_put(file_path=new_file_path, obj_dict=obj_dict, file_name=file_name,
                                   company_id=company_id):
            raise HTTPException(status_code=422, detail='Incorrect file path or new file name')
        if new_file_path + file_name in obj_dict:
            raise HTTPException(409, 'Destination image already exists')
        try:
            async with self.__get_client() as client:
                return await self._copy_versioned_plan(client,
                    [{'source':old_file_path + file_name, 'destination':new_file_path + file_name}], before_copy)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File not found")
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="Keys not found")
        except (ClientError, S3UploadFailedError) as e:
            raise HTTPException(status_code=422, detail=f"Error: {e.response['Error']['Message']}")

    async def _copy_versioned_plan(self, client, pairs, before_copy):
        plan = []
        etags = []
        for pair in pairs:
            metadata = await client.head_object(Bucket=self.bucket_name, Key=pair['source'])
            entry = dict(pair)
            version = metadata.get('VersionId')
            if version and version != 'null':
                entry['source_version'] = version
            plan.append(entry)
            etags.append(metadata.get('ETag'))
        if before_copy is not None:
            await before_copy(plan)
        completed = []
        for entry, etag in zip(plan, etags):
            source = {'Bucket':self.bucket_name, 'Key':entry['source']}
            if entry.get('source_version'):
                source['VersionId'] = entry['source_version']
            condition = {'CopySourceIfMatch':etag} if etag else {}
            result = await client.copy_object(Bucket=self.bucket_name, Key=entry['destination'],
                CopySource=source, **condition)
            if result['ResponseMetadata']['HTTPStatusCode'] != 200:
                raise HTTPException(503, 'Storage copy failed')
            item = dict(entry)
            version = result.get('VersionId')
            if version and version != 'null':
                item['destination_version'] = version
            completed.append(item)
        # Source deletion requires a separate, reference-aware cleanup operation.
        return completed

    async def delete_file(self, file_path: str, file_name: str, company_id: UUID):
        """
        Метод удаления файла по путям file_path
        :return: url
        """
        company_root = f'{BASE_STORAGE_DIRECTORY.COMPANY}company_{company_id}/'
        if (not file_path.startswith(company_root) or not file_path.endswith('/')
                or not file_name or '/' in file_name
                or any(part in ('.', '..') for part in (file_path + file_name).split('/'))):
            raise HTTPException(status_code=422, detail='Incorrect file path')
        # DeleteObject is idempotent: a missing object is already deleted.
        try:
            async with self.__get_client() as client:
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
        obj_dict = await self.get_object_metadata(file_path + file_name)
        if not check_path_getting(obj_path=file_path + file_name, obj_dict=obj_dict, company_id=company_id):
            raise HTTPException(status_code=422, detail='Incorrect file path')
        try:
            async with self.__get_client() as client:
                url = await client.generate_presigned_url(ClientMethod='get_object', ExpiresIn=600,
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
        obj_dict = await self.get_objects_by_dir_name(dir_name=file_path)
        if not check_file_path_put(file_path=file_path, obj_dict=obj_dict, file_name=file_name,
                                   company_id=company_id):
            raise HTTPException(status_code=422, detail='Incorrect file path or file name')
        storage_objects = await self.get_objects_by_dir_name(dir_name=f'company_images/company_{company_id}/')
        if not check_size_limits(obj_dict=storage_objects, file_size=file_size):
            raise HTTPException(status_code=422, detail='Incorrect file size')
        try:
            async with self.__get_client() as client:
                url = await client.generate_presigned_url(ClientMethod='put_object', ExpiresIn=IMAGE_UPLOAD_URL_TTL_SECONDS,
                                                          Params={'Bucket': self.bucket_name,
                                                                  'Key': file_path + file_name,
                                                                  'IfNoneMatch': '*',
                                                                  'ContentLength': int(file_size)})
                return url
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="Keys not found")
        except (ClientError, S3UploadFailedError) as e:
            raise HTTPException(status_code=422, detail=f"Error: {e.response['Error']['Message']}")

    async def upload_file(self, file: UploadFile, file_path: str, filename: str, company_id: UUID):
        """
        Метод динамической генерации преподписанного урла для загрузки файла
        :param filename: название файла
        :param file: файл изображения
        :param file_path: путь до файла
        :param company_id: id компании, где есть права для размещения изображения
        :return: url
        """
        if 'image' not in file.content_type:
            raise HTTPException(status_code=422, detail='Incorrect type file')
        obj_dict = await self.get_objects_by_dir_name(dir_name=file_path)
        if not check_file_path_put(file_path=file_path, obj_dict=obj_dict, file_name=filename,
                                   company_id=company_id):
            raise HTTPException(status_code=422, detail='Incorrect file path or file name')
        # Проверяем, что объем файла входит по лимитам как отдельно так и в сторедж
        storage_objects = await self.get_objects_by_dir_name(dir_name=f'company_images/company_{company_id}/')
        if not check_size_limits(obj_dict=storage_objects, file_size=file.size):
            raise HTTPException(status_code=422, detail='Incorrect file size')
        try:
            async with self.__get_client() as client:
                await client.put_object(Bucket=self.bucket_name, Key=file_path + filename,
                                        Body=await file.read(), ContentType=file.content_type, IfNoneMatch='*')
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="Keys not found")
        except ClientError as error:
            code = str(error.response.get('Error', {}).get('Code'))
            if code in ('PreconditionFailed', 'ConditionalRequestConflict', '412', '409'):
                raise HTTPException(409, 'Image already exists or was modified during upload') from None
            if code == 'AccessDenied':
                raise HTTPException(503, 'Storage write access denied') from None
            raise HTTPException(503, 'Storage temporarily unavailable') from None
        except S3UploadFailedError:
            raise HTTPException(503, 'Storage temporarily unavailable') from None

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
                obj_dict = await self.get_object_metadata(dir_path + dir_name)
                # Check company was not created early
                if dir_path + dir_name not in obj_dict.keys():
                    await client.put_object(Bucket=self.bucket_name, Key=f"{dir_path + dir_name}")
                else:
                    raise HTTPException(status_code=409,
                                        detail='Directory with name <{0}> already exist in storage'.format(dir_name))
        except NoCredentialsError:
            raise HTTPException(status_code=403, detail="Keys not found")
        except (ClientError, S3UploadFailedError) as e:
            raise HTTPException(status_code=422, detail=f"Error: {e.response['Error']['Message']}")

    async def rename_directory(self, dir_path: str, old_dir_name: str, new_dir_name: str, company_id: UUID, before_copy=None):
        from image.directory_move import directory_prefixes
        old_prefix, new_prefix = directory_prefixes(company_id, dir_path, old_dir_name, new_dir_name)
        if old_prefix == new_prefix:
            return
        obj_dict = await self.get_objects_by_dir_name(dir_name=dir_path)
        sources = [key for key in obj_dict if key.startswith(old_prefix)]
        if not sources:
            raise HTTPException(status_code=422, detail='Directory not exist')
        if any(key.startswith(new_prefix) for key in obj_dict):
            raise HTTPException(409, 'Destination directory already exists')
        try:
            async with self.__get_client() as client:
                return await self._copy_versioned_plan(client,
                    [{'source':key, 'destination':new_prefix + key[len(old_prefix):]} for key in sources], before_copy)
        except ClientError as e:
            raise HTTPException(status_code=422, detail=f"Error: {e.response['Error']['Message']}")

    async def delete_recorded_keys(self, keys, company_id):
        """Retry only the persisted manifest, never discover extra keys on retry."""
        root = f'{BASE_STORAGE_DIRECTORY.COMPANY}company_{company_id}/'
        if any(not isinstance(key, str) or not key.startswith(root) or '\\' in key
               or any(p in ('.', '..') for p in key.split('/')) for key in keys):
            raise HTTPException(422, 'Invalid deletion manifest')
        try:
            async with self.__get_client() as client:
                for offset in range(0, len(keys), 1000):
                    result = await client.delete_objects(Bucket=self.bucket_name,
                        Delete={'Objects': [{'Key': key} for key in keys[offset:offset + 1000]]})
                    if result.get('Errors') or result.get('ResponseMetadata', {}).get('HTTPStatusCode') != 200:
                        raise HTTPException(503, 'Directory deletion incomplete; retry required')
        except (ClientError, BotoCoreError):
            raise HTTPException(503, 'Storage temporarily unavailable') from None

    async def delete_directory(self, dir_path: str, dir_name: str, company_id: UUID):
        from image.directory_move import directory_prefixes
        prefix, _ = directory_prefixes(company_id, dir_path, dir_name, dir_name)
        try:
            async with self.__get_client() as client:
                paginator = client.get_paginator('list_objects_v2')
                delete_list = []
                async for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                    for obj in page.get('Contents', []):
                        key = obj.get('Key')
                        if not isinstance(key, str) or not key.startswith(prefix):
                            raise HTTPException(503, 'Invalid storage listing')
                        delete_list.append({'Key': key})
                # Collect first: listing failure must not leave a half-deleted folder.
                for offset in range(0, len(delete_list), 1000):
                    result = await client.delete_objects(Bucket=self.bucket_name,
                        Delete={'Objects': delete_list[offset:offset + 1000]})
                    if result.get('Errors') or result.get('ResponseMetadata', {}).get('HTTPStatusCode') != 200:
                        raise HTTPException(503, 'Directory deletion incomplete; retry required')
        except (ClientError, BotoCoreError):
            raise HTTPException(503, 'Storage temporarily unavailable') from None
