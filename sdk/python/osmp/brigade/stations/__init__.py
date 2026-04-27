"""Station experts — one per namespace. Each is pure: ParsedRequest → list[FrameProposal]."""
from .base import Station, BrigadeRegistry
from .r_station import RStation
from .e_station import EStation
from .h_station import HStation
from .n_station import NStation
from .c_station import CStation
from .a_station import AStation
from .g_station import GStation
from .v_station import VStation
from .w_station import WStation
from .t_station import TStation
from .i_station import IStation
from .s_station import SStation
from .k_station import KStation
from .b_station import BStation
from .u_station import UStation
from .l_station import LStation
from .m_station import MStation
from .d_station import DStation
from .j_station import JStation
from .f_station import FStation
from .o_station import OStation
from .p_station import PStation
from .q_station import QStation
from .x_station import XStation
from .y_station import YStation
from .z_station import ZStation


def default_registry() -> BrigadeRegistry:
    """Return a registry with all 26 namespace stations registered."""
    reg = BrigadeRegistry()
    for cls in (RStation, EStation, HStation, NStation, CStation, AStation,
                GStation, VStation, WStation, TStation, IStation, SStation,
                KStation, BStation, UStation, LStation, MStation, DStation,
                JStation, FStation, OStation, PStation, QStation, XStation,
                YStation, ZStation):
        reg.register(cls())
    return reg
