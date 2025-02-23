from fastapi import Depends
from starlette.background import BackgroundTasks

from app.crud.config.RedisConfigDao import PityRedisConfigDao
from app.handler.fatcory import PityResponse
from app.middleware.RedisManager import PityRedisManager
from app.models import DatabaseHelper
from app.models.redis_config import PityRedis
from app.models.schema.online_redis import OnlineRedisForm
from app.models.schema.redis_config import RedisConfigForm
from app.routers import Permission
from app.routers.config.environment import router
from config import Config


@router.get("/redis/list")
async def list_redis_config(name: str = '', addr: str = '', env: int = None,
                            cluster: bool = None,
                            user_info=Depends(Permission(Config.MEMBER))):
    try:
        data = await PityRedisConfigDao.list_record(
            name=DatabaseHelper.like(name), addr=DatabaseHelper.like(addr),
            env=env, cluster=cluster
        )
        return PityResponse.success(data=PityResponse.model_to_list(data))
    except Exception as err:
        return PityResponse.failed(err)


@router.post("/redis/insert")
async def insert_redis_config(form: RedisConfigForm,
                              user_info=Depends(Permission(Config.ADMIN))):
    try:
        query = await PityRedisConfigDao.query_record(name=form.name, env=form.env)
        if query is not None:
            raise Exception("数据已存在, 请勿重复添加")
        data = PityRedis(**form.dict(), user=user_info['id'])
        result = await PityRedisConfigDao.insert_record(data)
        return PityResponse.success(data=PityResponse.model_to_dict(result))
    except Exception as err:
        return PityResponse.failed(err)


@router.post("/redis/update")
async def update_redis_config(form: RedisConfigForm,
                              background_tasks: BackgroundTasks,
                              user_info=Depends(Permission(Config.ADMIN))):
    try:
        result = await PityRedisConfigDao.update_record_by_id(user_info['id'], form)
        if result.cluster:
            background_tasks.add_task(PityRedisManager.refresh_redis_cluster, *(result.id, result.addr))
        else:
            background_tasks.add_task(PityRedisManager.refresh_redis_client,
                                      *(result.id, result.addr, result.password, result.db))
        return PityResponse.success(data=PityResponse.model_to_dict(result))
    except Exception as err:
        return PityResponse.failed(err)


@router.get("/redis/delete")
async def delete_redis_config(id: int, background_tasks: BackgroundTasks,
                              user_info=Depends(Permission(Config.ADMIN))):
    try:
        ans = await PityRedisConfigDao.delete_record_by_id(user_info['id'], id)
        # 更新缓存
        background_tasks.add_task(PityRedisManager.delete_client, *(id, ans.cluster))
        return PityResponse.success()
    except Exception as err:
        return PityResponse.failed(err)


@router.post("/redis/command")
async def test_redis_command(form: OnlineRedisForm):
    try:
        res = await PityRedisConfigDao.execute_command(form.command, id=form.id)
        return PityResponse.success(res)
    except Exception as err:
        return PityResponse.failed(err)
