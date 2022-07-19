"""数据模型测试"""
from vxquant.utils import vxtime
from vxquant.utils.dataclass import (
    vxDataClass,
    vxDatetimeField,
    vxFloatField,
    vxIntField,
    vxPropertyField,
    vxUUIDField,
)
from vxquant.model.broker import vxOrder, vxTrade, vxAlgoOrder


def total(obj):
    """求和"""

    return obj.x + obj.y + obj.z


class vxTest(vxDataClass):
    """测试dataclass"""

    test_id = vxUUIDField()
    other_id = vxUUIDField(auto=False)
    x = vxIntField(0, -1, 10)
    y = vxFloatField(-0.5, 2, -7, 0)
    z = vxFloatField(0, 4, 0)
    due_dt = vxDatetimeField()
    div = vxPropertyField(lambda obj: obj.y / obj.x, 0)
    total = vxPropertyField(
        lambda obj: obj.y + obj.x + obj.z,
    )


def test_dataclass():
    """dataclass测试用例"""

    # dataclass基础功能测试

    # 缺省参数创建data
    data1 = vxTest()
    data2 = vxTest()
    data = vxTest()
    data1.x = 1.49999
    vxtime.sleep(0.1)
    data2.x = 2.5
    try:
        data2.y = 6
    except Exception as e:
        assert isinstance(e, ValueError)
        data2.y = -6

    print(data2)

    assert data.updated_dt == data.created_dt > 0
    assert len(data.test_id) > 0
    assert len(data.other_id) == 0
    assert data.x == 0
    assert data.y == -0.5
    assert data.z == 0
    assert data.total == -0.5
    assert data.div == 0

    assert data1.div == -0.5
    assert data2.div == -2

    data.z = 2
    assert data.created_dt < data.updated_dt

    pkl_data = vxTest.pack(data)
    other_data = vxTest.unpack(pkl_data)

    assert other_data == data
    other_data.z = 0.1
    data.z = 3
    assert other_data != data


if __name__ == "__main__":
    test_dataclass()
