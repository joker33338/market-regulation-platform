"""仅服务端构造的管理员数据范围，不能由请求字段或通配符配置伪造。"""


class AllOwners:
    def __contains__(self, value):
        return isinstance(value,str) and bool(value)


ALL_OWNERS=AllOwners()


def is_all_owners(value):
    return isinstance(value,AllOwners)
