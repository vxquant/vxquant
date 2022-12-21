""" 各类常量定义 """

from enum import Enum


class TradeTime(Enum):
    """交易时段"""

    DayBegin = "09:00:00"
    BeforeTrade = "09:15:00"
    OnTrade = "09:30:01"
    OnHans = "10:00:00"
    BeforeClose = "14:45:00"
    OnClose = "14:55:00"
    AfterClose = "15:30:00"
    DayEnd = "16:00:00"


class MarketSignal(Enum):
    """市场信号"""

    Bull = 1
    Monkey = 0
    Bear = -1
    Undefined = 99


class BarAdjustType(Enum):
    """复权形式"""

    NotAdj = 0  # 不复权
    PrevAdj = 1  # 前复权
    PostAdj = 2  # 后复权


class SecType(Enum):
    """标的类别"""

    CASH = 0  # 现金
    STOCK = 1  # 股票
    FUND = 2  # 基金
    INDEX = 3  # 指数
    FUTURE = 4  # 期货
    OPTION = 5  # 期权
    CREDIT = 6  # 信用交易
    BOND = 7  # 债券
    BOND_CONVERTIBLE = 8  # 可转债
    REPO = 9  # 回购
    CONFUTURE = 10  # 虚拟合约
    ETFLOF = 11  # ETF-LOF
    OTHER = 99  # 其他


class SecStatus(Enum):
    """标的状态"""

    NORMAL = 1  # -正常
    ST = 2  # -ST 股票,
    STAR_ST = 3  # -*ST 股票,
    TRANSFER = 4  # -股份转让,
    REARRANGEMENT = 5  # -处于退市整理期的证券,
    LOF = 6  # - 上市开放基金LOF,
    ETF = 7  # - 交易型开放式指数基金(ETF),
    OFUND_TRADE = 8  # - 非交易型开放式基金(暂不交易, 仅揭示基金净值及开放申购赎回业务),
    OFUND = 9  # - 仅提供净值揭示服务的开放式基金,
    SEC10 = 10  # - 仅在协议交易平台挂牌交易的证券,
    SEC11 = 11  # - 仅在固定收益平台挂牌交易的证券,
    SEC12 = 12  # - 风险警示产品,
    SEC13 = 13  # - 退市整理产品,
    OTHER = 99  # - 其它


class Exchange(Enum):
    """交易所代码
    上交所: SHSE
    深交所: SZSE
    中金所: CFFEX
    上期所: SHFE
    大商所: DCE
    郑商所: CZCE
    上海国际能源交易中心: INE
    """

    SHSE = "SHSE"
    SZSE = "SZSE"
    CFFEX = "CFFEX"
    SHFE = "SHFE"
    DCE = "DCE"
    CZCE = "CZCE"
    INE = "INE"
    OTHER = "OTHER"


class AccountType(Enum):
    """账户类型"""

    Normal = 0
    Credit = 1
    Unknown = 99


class OrderStatus(Enum):
    """委托状态"""

    Unknown = 0
    New = 1
    PartiallyFilled = 2
    Filled = 3
    Canceled = 5
    PendingCancel = 6
    Rejected = 8
    Suspended = 9
    PendingNew = 10
    Expired = 12


class OrderDirection(Enum):
    """委托方向"""

    Unknown = 0
    Buy = 1
    Sell = 2


class OrderOffset(Enum):
    """委托开平仓类型"""

    Unknown = 0
    Open = 1  # 开仓
    Close = 2  # 平仓, 具体语义取决于对应的交易所
    CloseToday = 3  # 平今仓
    CloseYesterday = 4  # 平昨仓


class OrderType(Enum):
    """委托类型"""

    Unknown = 0
    Limit = 1
    Market = 2
    Stop = 3
    Automated = 4
    T0TrailingStop = 5


class OrderDuration(Enum):
    """委托时间属性，仅实盘有效"""

    Unknown = 0
    FAK = 1  # 即时成交剩余撤销(fill and kill)
    FOK = 2  # 即时全额成交或撤销(fill or kill)
    GFD = 3  # 当日有效(good for day)
    GFS = 4  # 本节有效(good for section)
    GTD = 5  # 指定日期前有效(goodltilldate)
    GTC = 6  # 撤销前有效(goodtillcancel)
    GFA = 7  # 集合竞价前有效(good for auction)
    AHT = 8  # 盘后定价交易(after hour trading)


class OrderQualifier(Enum):
    """委托业务类型"""

    Unknown = 0
    BOC = 1  # 对方最优价格(best of counterparty)
    BOP = 2  # 己方最优价格(best of party)
    B5TC = 3  # 最优五档剩余撤销(best 5 then cancel)
    B5TL = 4  # 最优五档剩余转限价(best 5 then limit)


class TradeStatus(Enum):
    """成交回报类型"""

    Unknown = 0
    New = 1  # 已报
    Canceled = 5  # 已撤销
    PendingCancel = 6  # 待撤销
    Rejected = 8  # 已拒绝
    Suspended = 9  # 挂起
    PendingNew = 10  # 待报
    Expired = 12  # 过期
    Trade = 15  # 成交   (有效)
    OrderStatus = 18  # 委托状态
    CancelRejected = 19  # 撤单被拒绝  (有效)
    OrderFinalized = 101  # 委托已完成
    UnknownOrder = 102  # 未知委托
    BrokerOption = 103  # 柜台设置
    AlreadyInPendingCancel = 104  # 委托撤销中


class PositionEffect(Enum):
    """持仓头寸开平仓类型"""

    Unknown = 0
    Open = 1  # 开仓
    Close = 2  # 平仓, 具体语义取决于对应的交易所
    CloseToday = 3  # 平今仓
    CloseYesterday = 4  # 平昨仓


class PositionSide(Enum):
    """持仓方向"""

    Unknown = 0
    Long = 1  # 多方向
    Short = 2  # 空方向


class OrderRejectReason(Enum):
    """订单拒绝原因"""

    Unknown = 0  # 未知原因
    RiskRuleCheckFailed = 1  # 不符合风控规则
    NoEnoughCash = 2  # 资金不足
    NoEnoughPosition = 3  # 仓位不足
    IllegalAccountId = 4  # 非法账户ID
    IllegalStrategyId = 5  # 非法策略ID
    IllegalSymbol = 6  # 非法交易标的
    IllegalVolume = 7  # 非法委托量
    IllegalPrice = 8  # 非法委托价
    AccountDisabled = 10  # 交易账号被禁止交易
    AccountDisconnected = 11  # 交易账号未连接
    AccountLoggedout = 12  # 交易账号未登录
    NotInTradingSession = 13  # 非交易时段
    OrderTypeNotSupported = 14  # 委托类型不支持
    Throttle = 15  # 流控限制
    IllegalOrder = 103  # 交易委托不支持
    OrderFinalized = 101  # 委托已经完成
    UnknownOrder = 102  # 未知委托
    AlreadyInPendingCancel = 104  # 已经在撤单中


class CancelOrderRejectReason(Enum):
    """取消订单拒绝原因"""

    OrderFinalized = 101  # 委托已完成
    UnknownOrder = 102  # 未知委托
    BrokerOption = 103  # 柜台设置
    AlreadyInPendingCancel = 104  # 委托撤销中


class CashPositionChangeReason(Enum):
    """仓位变更原因"""

    Unknown = 0
    Trade = 1  # 交易
    Inout = 2  # 出入金 / 出入持仓


class AccountStatus(Enum):
    """交易账户状态"""

    UNKNOWN = 0  # 未知
    CONNECTING = 1  # 连接中
    CONNECTED = 2  # 已连接
    LOGGEDIN = 3  # 已登录
    DISCONNECTING = 4  # 断开中
    DISCONNECTED = 5  # 已断开
    ERROR = 6  # 错误


class PositionSrc(Enum):
    """头寸来源(仅适用融券融券)"""

    Unknown = 0
    L1 = 1  # 普通池
    L2 = 2  # 专项池


class AlgoOrderStatus(Enum):
    """组合委托状态"""

    Unknown = 99  # 未知
    New = 0  # 新增
    Operating = 1  # 运行中
    Completed = 2  # 已完成
    Canceled = 3  # 已撤销
    Stopped = 4  # 已暂停
    Expired = 5  # 已过期


class AlgoOrderType(Enum):
    """算法委托类型"""

    Unknown = 0  # 未知
    Rebalance = 1  # 组合
    AssetGrids = 3  # 市值网格
    T0Bot = 4  # T+0机器人
