# encoding=utf-8
""" 委托及成交回报 数据模型 """
from vxquant.utils.dataclass import (
    vxDataClass,
    vxField,
    vxPropertyField,
    vxUUIDField,
    vxEnumField,
    vxFloatField,
    vxIntField,
    vxBoolField,
    vxDatetimeField,
)

from vxquant.model.contants import (
    TradeStatus,
    OrderType,
    OrderStatus,
    OrderDirection,
    OrderOffset,
    PositionSide,
    OrderRejectReason,
    AlgoOrderStatus,
    AlgoOrderType,
    SecType,
    SecStatus,
)
from vxquant.utils import vxtime


__all__ = [
    "vxTrade",
    "vxOrder",
    "vxAlgoOrder",
    "vxPosition",
    "vxCashPosition",
    "vxAccountInfo",
    "vxPortfolioInfo",
    "vxTick",
    "vxBar",
]


def _filled_vwap(vxorder: "vxOrder") -> float:
    """成交均价"""
    return round(vxorder.filled_amount / vxorder.filled_volume, 4)


class vxTrade(vxDataClass):
    """成交回报"""

    # 账户id
    account_id: str = vxUUIDField(False)
    # 委托id
    order_id: str = vxUUIDField(False)
    # 交易所委托id
    exchange_order_id: str = vxUUIDField(False)
    # 成交id
    trade_id: str = vxUUIDField()
    # 证券代码
    symbol: str = vxField("", str)
    # 买卖方向
    order_direction: OrderDirection = vxEnumField(OrderDirection.Unknown)
    # 开平仓标志
    order_offset: OrderOffset = vxEnumField(OrderOffset.Unknown)
    # 成交价格
    price: float = vxFloatField(0, ndigits=2, _min=0.0)
    # 成交数量
    volume: int = vxIntField(0, _min=0)
    # 交易佣金
    commission: float = vxFloatField(0, ndigits=2, _min=0.0)
    # 成交状态
    status: TradeStatus = vxEnumField(TradeStatus.Unknown)
    # 拒绝代码
    reject_code: OrderRejectReason = vxEnumField(OrderRejectReason.Unknown)
    # 拒绝原因
    reject_reason: str = vxField("", str)


class vxOrder(vxDataClass):
    """委托订单"""

    # 账号id
    account_id: str = vxUUIDField(False)
    # 算法委托id
    algo_order_id: str = vxUUIDField(False)
    # 交易所委托id
    exchange_order_id: str = vxUUIDField(False)
    # 冻结持仓id
    frozen_position_id: str = vxUUIDField(False)
    # 委托id
    order_id: str = vxUUIDField()
    # 证券代码
    symbol: str = vxField("", str)
    # 买卖方向
    order_direction: OrderDirection = vxEnumField(OrderDirection.Unknown)
    # 开平仓标志
    order_offset: OrderOffset = vxEnumField(OrderOffset.Unknown)
    # 订单类型
    order_type: OrderType = vxEnumField(OrderType.Unknown)
    # 委托数量
    volume: int = vxIntField(0, _min=0)
    # 委托价格
    price: float = vxFloatField(0.0, 2, _min=0)
    # 成交数量
    filled_volume: int = vxIntField(0, _min=0)
    # 成交均价
    filled_vwap: float = vxPropertyField(_filled_vwap, 0.0)
    # 成交总额（含手续费）
    filled_amount: float = vxFloatField(0.0, 2)
    # 订单状态
    status: OrderStatus = vxEnumField(OrderStatus.PendingNew)
    # 拒绝代码
    reject_code: OrderRejectReason = vxEnumField(OrderRejectReason.Unknown)
    # 拒绝原因
    reject_reason: str = vxField(default_factory="", convertor_factory=str)
    # 订单超时时间
    due_dt: float = vxDatetimeField(default_factory=lambda: vxtime.today("15:00:00"))


class vxAlgoOrder(vxDataClass):
    """算法订单"""

    # 账户id
    account_id: str = vxUUIDField(False)
    # 算法委托id
    algo_order_id: str = vxUUIDField()
    # 算法委托类型
    algo_order_type: AlgoOrderType = vxEnumField(AlgoOrderType.Unknown)
    # 算法委托参数
    params: dict = vxField(default_factory={})
    # 算法委托状态
    status: AlgoOrderStatus = vxEnumField(AlgoOrderStatus.Unknown)
    # 订单超时时间
    due_dt: float = vxDatetimeField(default_factory=lambda: vxtime.today("15:00:00"))


def _available_volume(obj):
    """可用仓位计算规则"""
    return max(
        (obj.volume - obj.frozen) if obj.allow_t0 else obj.volume_his - obj.frozen, 0
    )


class vxPosition(vxDataClass):
    """股票持仓"""

    # 组合ID
    portfolio_id: str = vxUUIDField(False)
    # 账户id
    account_id: str = vxUUIDField(False)
    # 仓位id
    position_id: str = vxUUIDField()
    # 证券类型
    security_type: SecType = vxEnumField(SecType.OTHER)
    # 证券代码
    symbol: str = vxField("", str)
    # 持仓方向
    position_side: PositionSide = vxEnumField(PositionSide.Long)
    # 今日持仓数量
    volume_today: int = vxIntField(0, 0)
    # 昨日持仓数量
    volume_his: int = vxIntField(0, 0)
    # 持仓数量
    volume: int = vxPropertyField(
        lambda obj: obj.volume_his + obj.volume_today, default_factory=0
    )
    # 冻结数量
    frozen: int = vxIntField(0, 0)
    # 可用数量
    available: int = vxPropertyField(_available_volume, default_factory=0)
    # 持仓市值
    marketvalue: float = vxPropertyField(
        lambda obj: round(obj.volume * obj.lasttrade, 2), default_factory=0
    )
    # 持仓成本
    cost: float = vxFloatField(0, 2)
    # 浮动盈利
    fnl: float = vxPropertyField(lambda obj: obj.marketvalue - obj.cost, 0)
    # 持仓成本均价
    vwap: float = vxPropertyField(lambda obj: round(obj.cost / obj.volume, 4), 0)
    # 最近成交价
    lasttrade: float = vxFloatField(1.0, 4)
    # 是否T0
    allow_t0: bool = vxBoolField(False)


class vxCashPosition(vxDataClass):
    """现金持仓"""

    # 组合ID
    portfolio_id: str = vxUUIDField(False)
    # 账户id
    account_id: str = vxUUIDField(False)
    # 仓位id
    position_id: str = vxUUIDField()
    # 证券类型
    security_type: SecType = vxEnumField(SecType.CASH)
    # 证券代码
    symbol: str = vxField("CNY", str)
    # 持仓方向
    position_side: PositionSide = vxEnumField(PositionSide.Long)
    # 今日持仓数量
    volume_today: float = vxFloatField(0, 2, 0)
    # 昨日持仓数量
    volume_his: float = vxFloatField(0, 2, 0)
    # 持仓数量
    volume: int = vxPropertyField(
        lambda obj: obj.volume_his + obj.volume_today, default_factory=0
    )
    # 冻结数量
    frozen: int = vxFloatField(0, 2, 0)
    # 可用数量
    available: int = vxPropertyField(_available_volume, default_factory=0)
    # 持仓市值
    marketvalue: float = vxPropertyField(
        lambda obj: obj.volume_his + obj.volume_today, default_factory=0
    )
    # 持仓成本
    cost: float = vxPropertyField(
        lambda obj: obj.volume_his + obj.volume_today, default_factory=0
    )
    # 浮动盈利
    fnl: float = vxPropertyField(lambda obj: 0, 0)
    # 持仓成本均价
    vwap: float = vxPropertyField(lambda obj: 1.0, 1.0)
    # 最近成交价
    lasttrade: float = vxPropertyField(lambda obj: 1.0, default_factory=1.0)
    # 是否T0
    allow_t0: bool = vxBoolField(True)


class vxAccountInfo(vxDataClass):
    """账户信息类型"""

    # 组合ID
    portfolio_id: str = vxUUIDField(False)
    # 账户id
    account_id: str = vxUUIDField()
    # 账户币种
    currency: str = vxField("CNY")
    # 今日转入金额
    deposit: float = vxFloatField(0, 2, 0)
    # 今日转出金额
    withdraw: float = vxFloatField(0, 2, 0)
    # 总资产
    asset: float = vxPropertyField(lambda obj: obj.balance + obj.marketvalue, 0)
    # 净资产
    nav: float = vxPropertyField(lambda obj: obj.asset - obj.debt)
    # 总负债
    debt: float = vxFloatField(0, 2)
    # 资金余额
    balance: float = vxFloatField(0, 2)
    # 冻结金额
    frozen: float = vxFloatField(0, 2)
    # 可用金额
    available: float = vxPropertyField(lambda obj: max(obj.balance - obj.frozen, 0), 0)
    # 融资融券可用
    margin_available: float = vxFloatField(0, 2)
    # 总市值
    marketvalue: float = vxFloatField(0, 2)
    # 今日盈利
    today_profit: float = vxPropertyField(
        lambda obj: obj.nav - obj.nav_yd + obj.doposit - obj.withdraw, 0
    )
    # 浮动盈亏
    fnl: float = vxFloatField(0, 2)
    # 基金份额
    fund_shares: float = vxFloatField(0, 4)
    # 基金净值估算
    fund_nav: float = vxPropertyField(
        lambda obj: round(obj.nav / obj.fund_shares, 4), 1.0
    )
    # 昨日总资产
    asset_yd: float = vxFloatField(0, 2)
    # 昨日净资产
    nav_yd: float = vxFloatField(0, 2)
    # 昨日基金金额
    fund_nav_yd: float = vxFloatField(1, 4)


class vxPortfolioInfo(vxDataClass):
    """组合信息"""

    # 组合id
    portfolio_id: str = vxUUIDField(True)
    # 组合名称
    name: str = vxField("", str)
    # 组合说明
    description: str = vxField("", str)
    # 业绩基准
    benchmark: str = vxField("SHSE.000300", str)
    # 基金净资产
    nav: float = vxFloatField(0.0, 2)
    # 昨日基金净值
    nav_yd: float = vxFloatField(0.0, 2)
    # 基金净值
    fund_nav: float = vxPropertyField(
        lambda obj: round(obj.nav / obj.fund_shares, 4), 1.0
    )
    # 昨日基金净值
    fund_nav_yd: float = vxPropertyField(
        lambda obj: round(obj.nav / obj.fund_shares, 4), 1.0
    )
    # 基金份额
    fund_shares: float = vxFloatField(1.0, 4)
    # 管理人
    manager: str = vxField("", str)


class vxTick(vxDataClass):
    """行情模型"""

    # 证券标的
    symbol: str = vxField("", str)
    # 开盘价
    open: float = vxFloatField(0, 4)
    # 最高价
    high: float = vxFloatField(0, 4)
    # 最低价
    low: float = vxFloatField(0, 4)
    # 最近成交价
    lasttrade: float = vxFloatField(0, 4)
    # 昨日收盘价
    yclose: float = vxFloatField(0, 4)
    # 成交量
    volume: int = vxIntField(0, 0)
    # 成交金额
    amount: float = vxFloatField(0, 4)
    # 卖1量
    bid1_v: float = vxFloatField(0, 4)
    # 卖1价
    bid1_p: int = vxIntField(0, 0)
    # 卖2量
    bid2_v: float = vxFloatField(0, 4)
    # 卖2价
    bid2_p: int = vxIntField(0, 0)
    # 卖3量
    bid3_v: float = vxFloatField(0, 4)
    # 卖3价
    bid3_p: int = vxIntField(0, 0)
    # 卖4量
    bid4_v: float = vxFloatField(0, 4)
    # 卖4价
    bid4_p: int = vxIntField(0, 0)
    # 卖5量
    bid5_v: float = vxFloatField(0, 4)
    # 卖5价
    bid5_p: int = vxIntField(0, 0)
    # 买1量
    ask1_v: float = vxFloatField(0, 4)
    # 买1价
    ask1_p: int = vxIntField(0, 0)
    # 买2量
    ask2_v: float = vxFloatField(0, 4)
    # 买2价
    ask2_p: int = vxIntField(0, 0)
    # 买3量
    ask3_v: float = vxFloatField(0, 4)
    # 买3价
    ask3_p: int = vxIntField(0, 0)
    # 买4量
    ask4_v: float = vxFloatField(0, 4)
    # 买4价
    ask4_p: int = vxIntField(0, 0)
    # 买5量
    ask5_v: float = vxFloatField(0, 4)
    # 买5价
    ask5_p: int = vxIntField(0, 0)
    # 持仓量
    interest: int = vxIntField(0, 0)
    # 停牌状态
    status: SecStatus = vxEnumField(SecStatus.NORMAL)


class vxBar(vxDataClass):
    """K线模型"""

    # 证券标的
    symbol: str = vxField("", str)
    # 周期
    frequency: str = vxField("", str)
    # 开盘价
    open: float = vxFloatField(0, 4)
    # 最高价
    high: float = vxFloatField(0, 4)
    # 最低价
    low: float = vxFloatField(0, 4)
    # 收盘价
    close: float = vxFloatField(0, 4)
    # 昨收盘价
    yclose: float = vxFloatField(0, 4)
    # 成交金额
    amount: float = vxFloatField(0, 4)
    # 成交量
    volume: int = vxIntField(0, 0)
    # 持仓量
    interest: int = vxIntField(0, 0)
