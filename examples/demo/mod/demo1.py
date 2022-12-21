"""策略demo 1 """

from vxsched import vxengine, vxEvent, vxContext, logger


@vxengine.event_handler("__init__")
def demo1_init(context: vxContext, event: vxEvent) -> None:
    """策略初始化"""
    logger.info(f"title内容: {context.settings.title}")


@vxengine.event_handler("every_tick")
def demo1_every_tick(context: vxContext, event: vxEvent) -> None:
    """每个tick事件触发"""
    logger.info(f"触发时间: {event.type}")