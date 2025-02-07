import boto3
from botocore.config import Config
from botocore.exceptions import NoCredentialsError, ClientError
from s3transfer import S3UploadFailedError

from settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

import logging

# logging.basicConfig(level=logging.DEBUG)
# boto3.set_stream_logger('')

# s3 = boto3.client(
#     service_name='s3',
#     endpoint_url='https://storage.yandexcloud.net',
#     aws_access_key_id=AWS_ACCESS_KEY_ID,
#     aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
#     region_name='ru-central1'
# )

# try:
#     s3.upload_file(
#         Filename='test11.txt',  # путь к локальному файлу
#         Bucket='culta-images',  # имя бакета (создай его через консоль Yandex)
#         Key='file_in_s3.txt'  # имя файла в облаке
#     )
#     print("Файл успешно загружен!")
# except NoCredentialsError:
#     print("Ошибка: ключи доступа не найдены.")
# except ClientError as e:
#     print(f"Ошибка: {e.response['Error']['Message']}")

# try:
#     with open('test11.txt', 'rb') as file:
#         s3.put_object(
#             Bucket='culta-new',
#             Key='file_in_s3.txt',
#             Body=file
#         )
#     print("Файл успешно загружен!")
# except ClientError as e:
#     print(f"Ошибка: {e.response['Error']['Message']}")



# Проверка доступа
# try:
#     response = s3.list_buckets()
#     print("Бакеты:", [b['Name'] for b in response['Buckets']])
# except Exception as e:
#     print(f"Ошибка: {e}")


# def list_bucket_objects(bucket_name):
#     try:
#         response = s3.list_objects_v2(Bucket=bucket_name)
#         if 'Contents' in response:
#             for obj in response['Contents']:
#                 print(f"Объект: {obj['Key']}, Размер: {obj['Size']} байт")
#         else:
#             print("Бакет пуст.")
#     except Exception as e:
#         print(f"Ошибка: {e}")
#
#
# # Пример использования
# list_bucket_objects('culta-images')

# s3.download_file(
#     Bucket='culta-images',
#     Key='test1.txt',
#     Filename='test1.txt'
# )
#
#
# def upload_file(bucket_name, file_name, object_name=None):
#     if object_name is None:
#         object_name = file_name
#
#     try:
#         with open(file_name, 'rb') as file:
#             s3.put_object(
#                 Bucket=bucket_name,
#                 Key=object_name,
#                 Body=file
#             )
#         print(f"Файл {file_name} успешно загружен как {object_name}.")
#     except FileNotFoundError:
#         print(f"Файл {file_name} не найден.")
#     except NoCredentialsError:
#         print("Ключи доступа не найдены.")
#     except ClientError as e:
#         print(f"Ошибка: {e.response['Error']['Message']}")
#
#
# # Пример использования
# upload_file('culta-images', 'test11.txt', 'file_in_s3.txt')

s3 = boto3.client(
    service_name='s3',
    endpoint_url='https://storage.yandexcloud.net',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name='ru-central1'
)

# s3.download_file(
#     Bucket='culta-images',
#     Key='image.jpg',
#     Filename='image.jpg'
# )


try:
    s3.upload_file(
        Filename='image.jpg',  # путь к локальному файлу
        Bucket='culta-images',  # имя бакета (создай его через консоль Yandex)
        Key='company_0101/image.jpg',  # имя файла в облаке
    )
    print("Файл загружен!")
except S3UploadFailedError as e:
    print(f"Ошибка: {e.response['Error']['Message']}")


# url = s3.generate_presigned_url(
#     ClientMethod='get_object',  # или 'put_object' для загрузки
#     Params={
#         'Bucket': 'culta-images',
#         'Key': 'image.jpg'
#     },
#     ExpiresIn=120  # срок жизни ссылки в секундах (1 час)
# )
#
# print("Подписанный URL:", url)











