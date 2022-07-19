"""zmq channel 服务器"""
import argparse
from vxquant.scheduler.channels.zmqchannel import vxZMQChannelServer


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="""zmq channel 服务器""")
    parser.add_argument(
        "--host",
        help="bind ip address,default: any ip address on the server",
        default="*",
        type=str,
    )
    parser.add_argument(
        "-p",
        "--port",
        help="bind ports,default: 5555",
        default=5555,
        type=int,
    )
    parser.add_argument(
        "-k", "--keyfile", help="private key file path", default="", type=str
    )
    args = parser.parse_args()
    url = f"tcp://{args.host}:{args.port}"
    server = vxZMQChannelServer(url, args.keyfile)
    server.start()
