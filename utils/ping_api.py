from fastapi import APIRouter

service_router = APIRouter()


@service_router.get('/ping')
async def ping():
    return {'Success': True}


@service_router.get('/ping_test')
async def ping():
    return {'Миша': 'Ты рыбу собрал?',
            'Саша': 'Ты данные выгрузил?'}
