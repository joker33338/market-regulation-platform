"""知识库版本生命周期管理，与候选入库及在线检索分离。

版本构建不等于发布；调用方必须通过权限、来源及审核门禁后才能切换活动版本。"""
from qa_core.storage.database import Database


def publish(database: Database, version: str, **guards) -> dict:
    database.publish(version, **guards)
    return {"version": version, "status": "ACTIVE", "action": "publish"}


def rollback(database: Database, version: str, **guards) -> dict:
    database.publish(version, rollback=True, **guards)
    return {"version": version, "status": "ACTIVE", "action": "rollback"}

