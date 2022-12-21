""" run zmq broker"""

import zmq
import argparse

import contextlib
from collections.abc import Mapping

from itertools import chain
from queue import Queue, Empty
from vxutils import logger, vxZMQContext, to_binary, storage, vxtime, vxWrapper

from vxsched.core import vxengine
from vxsched.triggers import vxDailyTrigger
from vxsched.event import vxEvent, vxEventQueue


def init_socket(socket_type, settings):
    ctx = vxZMQContext().instance()
    socket_ = ctx.socket(socket_type)
    if settings["connect_mode"].lower() == "connect":
        socket_.connect(settings["addr"], settings["public_key"])
    else:
        socket_.bind(settings["addr"], settings["public_key"])
    return socket_


def on_recv_frontend_msg(engine, msgs):
    client_addr, empty, packed_event = msgs
    assert empty == b""
    event = vxEvent.unpack(packed_event)

    context = engine.context
    logger.debug(f"frontend 收到来自 {client_addr} 消息: {event}")
    if event.channel == "__BROKER__":
        event.reply_to = client_addr
        engine.submit_event(event)
    elif event.channel == "__RPC__":
        if event.type in context.rpc_methods:
            event.reply_to = client_addr
            event.channel = context.rpc_methods[event.type]
            context.backend_queue.put_nowait(event)
        else:
            context.frontend_queue.put_nowait(
                vxEvent(
                    type="__RPC_REPLY__",
                    data=AttributeError(f"不支持的远程调用方法: {event.type}"),
                    channel=client_addr,
                )
            )
    elif event.type.startswith("_"):
        context.frontend_queue.put_nowait(
            vxEvent(
                type="__ACK__",
                data=ValueError(f"not suport event.type({event.type})"),
                channel=client_addr,
            )
        )
    else:
        event.reply_to = ""
        context.backend_queue.put_nowait(event)
        context.frontend_queue.put_nowait(
            vxEvent(type="__ACK__", data="OK", channel=client_addr)
        )


def on_recv_backend_msg(engine, msgs):
    context = engine.context
    try:
        if msgs[0].startswith(b"\x01"):
            engine.submit_event(
                vxEvent(
                    type="__ON_SUBSCRIBE__",
                    data=msgs[0][1:].decode("ascii"),
                    channel="__BROKER__",
                )
            )
            return

        if msgs[0].startswith(b"\x00"):
            engine.submit_event(
                vxEvent(
                    type="__ON_UNSUBSCRIBE__",
                    data=msgs[0][1:].decode("ascii"),
                    channel="__BROKER__",
                )
            )
            return

        _, packed_event = msgs
        event = vxEvent.unpack(packed_event)
        if event.channel == "__BROKER__":
            engine.submit_event(event)
        elif event.channel:
            context.frontend_queue.put(event)
        else:
            logger.warning(f"收到错误消息: {event}")

    except Exception as e:
        logger.error(f"error: {e}", exc_info=True)


@vxengine.backend
def run_broker_backend(engine):
    context = engine.context
    context.backend_queue = vxEventQueue()
    context.frontend_queue = Queue()
    context.rpc_methods = {}

    for event_type, trigger_params in context.settings.events.items():
        if isinstance(trigger_params, Mapping):
            trigger = vxWrapper.init_by_config(trigger_params)
        elif isinstance(trigger_params, str):
            trigger = vxDailyTrigger(run_time=trigger_params)
        else:
            logger.error(f"不符合设置: {event_type} == {trigger_params}. ")
        preset_event = vxEvent(type=event_type, trigger=trigger, channel="__BROKER__")
        context.backend_queue.put(preset_event)
        logger.info(f"提交预设事件: {preset_event}")

    frontend = init_socket(zmq.ROUTER, context.settings.frontend)
    backend = init_socket(zmq.XPUB, context.settings.backend)

    poller = zmq.Poller()
    poller.register(frontend, zmq.POLLIN | zmq.POLLOUT)
    poller.register(backend, zmq.POLLIN | zmq.POLLOUT)

    while engine.is_alive():
        flags = dict(poller.poll(1000))

        if frontend in flags and flags[frontend] & zmq.POLLIN != 0:
            msgs = frontend.recv_multipart()
            logger.debug(f"frontend msgs: {msgs}")
            on_recv_frontend_msg(engine, msgs)

        if backend in flags and flags[backend] & zmq.POLLIN != 0:
            msgs = backend.recv_multipart()
            logger.debug(f"backend msgs: {msgs}")
            on_recv_backend_msg(engine, msgs)

        if frontend in flags and flags[frontend] & zmq.POLLOUT != 0:
            with contextlib.suppress(Empty):
                event = context.frontend_queue.get(timeout=0.05)
                frontend.send_multipart(
                    [to_binary(event.channel), b"", vxEvent.pack(event)]
                )
                logger.debug(
                    f"fronend 发送消息 {event.type} ({event.data})--> {event.channel}"
                )

        if backend in flags and flags[backend] & zmq.POLLOUT != 0:
            with contextlib.suppress(Empty):
                event = context.backend_queue.get(timeout=0.05)
                backend.send_multipart([to_binary(event.channel), vxEvent.pack(event)])
                logger.debug(
                    f"backend 发送消息: {event.type} ({event.data}) --> {event.channel}"
                )
        # vxtime.sleep(0.1)


@vxengine.event_handler("__ON_SUBSCRIBE__")
def backend_on_subscribe(context, event) -> None:
    """订阅事件触发"""
    logger.error(f"收到订阅信息: {event.data} =====")
    if event.data.startswith("rpc_"):
        context.backend_queue.put_nowait(
            vxEvent(
                type="__GET_RPCMETHODS__", channel=event.data, reply_to="__BROKER__"
            )
        )


@vxengine.event_handler("__ON_UNSUBSCRIBE__")
def backend_on_unsubscribe(context, event) -> None:
    logger.warning(f"取消订阅信息: {event.data}")
    if event.data.startswith("rpc_"):
        context.rpc_methods = {
            method: channel
            for method, channel in context.rpc_methods.items()
            if channel != event.data
        }


def handle_subscribers(context, event) -> None:
    """处理外部获取的消息"""

    # logger.debug(f"开始抓取subscriber ({context.subscribers})中的消息")
    if not context.subscribers:
        return

    events = [subscriber() for subscriber in context.subscribers]
    for event in chain(*events):
        context.event_queue.put_nowait(event)
        logger.info(f"internal: 收到外部event : ({event.type})")

    return


@vxengine.event_handler("__GET_RPCMETHODS__")
def frontend_handle_get_rpc_method(context, event):
    """前端或许rpc methods"""
    reply_event = vxEvent(
        type="__GET_RPCMETHODS__",
        data=context.rpc_methods,
        channel=event.reply_to,
    )
    context.frontend_queue.put_nowait(reply_event)


@vxengine.event_handler("__RPC_METHODS__")
def backend_on_update_methods(context, event):
    """更新rpc methods"""

    if isinstance(event.data, Exception):
        logger.warning(f"更新rpc methods 错误: {event.data}")
    else:
        logger.warning(f"更新rpc method: {event.data}")
        context.rpc_methods.update(event.data)


@vxengine.event_handler("__READY__")
def frontend_ready_event(context, event):
    """处理前端的ready消息"""
    reply_event = vxEvent(
        type="__ACK__",
        data="OK",
        channel=event.reply_to,
    )
    context.frontend_queue.put_nowait(reply_event)
    logger.info(f"发送frontend 消息: {reply_event}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""scheduler server""")
    parser.add_argument("-s", "--script", help="启动组件", default="broker")
    parser.add_argument(
        "-c",
        "--config",
        help="path to config json file",
        default="config.json",
        type=str,
    )
    parser.add_argument("-m", "--mod", help="模块存放目录", default="./mod", type=str)
    parser.add_argument(
        "-v", "--verbose", help="debug 模式", action="store_true", default=False
    )
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel("DEBUG")

    func = storage.get("scheduler", args.script)

    if callable(func):
        func(args.config, args.mod)
