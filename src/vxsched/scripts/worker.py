""" run zmq worker"""

import zmq
import argparse
import pathlib
import contextlib
from queue import Queue, Empty
from vxutils import logger, vxZMQContext, to_binary, to_text, storage, vxtime
from vxsched.context import vxContext
from vxsched.core import vxengine
from vxsched.event import vxEvent
from vxsched.rpc import rpcwrapper


@vxengine.event_handler("__init__")
def init_worker(context, event):
    context.reply_queue = Queue()
    logger.info(f"初始化 workder: {context}")


@vxengine.event_handler("__GET_RPCMETHODS__")
def on_recv_msg(context, event):
    reply_event = vxEvent(
        type="__RPC_METHODS__",
        data=rpcwrapper.methods,
        channel="__BROKER__",
    )
    context.reply_queue.put_nowait(reply_event)
    logger.info(f"注册rpc method: {reply_event.data}")


@vxengine.event_handler("__RPC_CALL__")
def handle_rpc_call(context, event):
    rpc_event = event.data
    args, kwargs = rpc_event.data
    try:
        reply_msg = rpcwrapper(rpc_event.type, *args, **kwargs)
    except Exception as e:
        reply_msg = e
        logger.error(f"运行错误： {reply_msg}", exc_info=True)

    context.reply_queue.put_nowait(
        vxEvent(
            type=rpc_event.type,
            data=rpc_event.data,
            channel=rpc_event.reply_to,
        )
    )


def create_socket(engine):
    zmqbackend_settings = engine.context.settings["zmqbackend"]

    addr = zmqbackend_settings["addr"]
    public_key = zmqbackend_settings["public_key"]
    connect_mode = zmqbackend_settings["connect_mode"].lower()

    ctx = vxZMQContext()
    socket = ctx.socket(zmq.XSUB)

    if connect_mode == "connect":
        socket.connect(addr, public_key)
    else:
        socket.bind(addr, public_key)

    socket.send(b"\x01" + to_binary("__BROKER__"))
    logger.info("订阅缺省消息通道: __BROKER__")

    channels = zmqbackend_settings["channels"]
    for channel in channels:
        socket.send(b"\x01" + to_binary(channel))
        logger.info(f"订阅消息通道: {channel}")

    if rpcwrapper.methods:
        socket.send(b"\x01" + to_binary(rpcwrapper.rpc_token))
        logger.info(f"订阅RPC通道: {rpcwrapper.rpc_token}")
        engine.submit_event("__GET_RPCMETHODS__")

    return socket


@vxengine.backend
def zmqbackend(engine):
    socket = create_socket(engine)
    while engine.is_alive():
        flags = socket.poll(1000, zmq.POLLIN | zmq.POLLOUT)
        try:
            if flags & zmq.POLLIN != 0:
                channel, packed_event = socket.recv_multipart()
                channel = to_text(channel)
                recv_event = vxEvent.unpack(packed_event)
                logger.debug(f"收到来自{channel} 发送消息: {recv_event.type}")
                if channel.startswith("rpc_"):
                    engine.submit_event("__RPC_CALL__", recv_event)
                else:
                    engine.submit_event(recv_event)

            if flags & zmq.POLLOUT != 0:
                with contextlib.suppress(Empty):
                    rpc_reply = engine.context.reply_queue.get(timeout=0.1)
                    msgs = [to_binary(rpc_reply.channel), vxEvent.pack(rpc_reply)]
                    socket.send_multipart(msgs)
        except Exception as err:
            logger.warning(f"运行时错误: {err}", exc_info=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""worker server""")
    parser.add_argument("-s", "--script", help="启动组件", default="worker")
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
