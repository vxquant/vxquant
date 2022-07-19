from cgi import test
from vxquant.scheduler.event import vxEvent
from vxquant.scheduler.channels import vxChannel
from vxquant.scheduler.triggers import vxTrigger, vxOnceTrigger
from vxquant.utils import vxtime
from queue import PriorityQueue


def test_event() -> None:
    now = vxtime.now()
    q = PriorityQueue()

    event1 = vxEvent(type="test1", data="", next_trigger_dt=now, priority=10)
    event2 = vxEvent(type="test2", data="", next_trigger_dt=now, priority=9)
    event3 = vxEvent(type="test3", data="", next_trigger_dt=now + 1, priority=10)
    event4 = vxEvent(type="test4", data="", next_trigger_dt=now + 1, priority=2)
    event5 = vxEvent(type="test5", data="", next_trigger_dt=now, priority=10)
    q.put(event1)
    q.put(event2)
    q.put(event3)
    q.put(event4)
    q.put(event5)

    assert event1 > event2
    assert event1 < event3
    assert event4 > event5
    e = q.get()
    assert e.type == event2.type
    e = q.get()
    assert e.type == event1.type
    e = q.get()
    assert e.type == event5.type
    e = q.get()
    assert e.type == event4.type
    e = q.get()
    assert e.type == event3.type


def test_channel():
    """测试通道"""
    test_channel1 = vxChannel("test")
    test_channel2 = vxChannel("test")
    assert test_channel1 == test_channel2
    assert len(test_channel1._queue_pools) == 1
    test_channel3 = vxChannel("test3")
    assert len(test_channel3._queue_pools) == 2

    now = vxtime.now()

    test_channel1.put("test_event", priority=3, trigger=vxOnceTrigger(now + 100))
    test_channel1.put("test_event2", priority=2, trigger=vxOnceTrigger(now + 100))
    test_channel1.put("test_event3", priority=3, trigger=vxOnceTrigger(now + 30))
    test_channel1.put("test_event4", priority=3, trigger=vxOnceTrigger(now + 99))
    e = test_channel1.get(now, timeout=0.1)
    assert e is None
    e = test_channel1.get(timeout=0.1)
    assert e.type == "test_event3"
    e = test_channel1.get(timeout=0.1)
    assert e.type == "test_event4"
    e = test_channel1.get(timeout=0.1)
    assert e.type == "test_event2"
    e = test_channel1.get(timeout=0.1)
    assert e.type == "test_event"


def test_scheduler():
    """测试调度器"""
