from fastapi import APIRouter

service_router = APIRouter()


@service_router.get('/pong')
async def ping():
    return {'Success': True}


@service_router.get('/pong_friends')
async def ping():
    return {'Миша': 'Ты рыбу собрал?',
            'Саша': 'Ты данные выгрузил?'}
