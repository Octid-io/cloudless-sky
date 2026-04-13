export const FLAG_TERMINAL = 0b00000001;
export const FLAG_CRITICAL = 0b00000010;
export const FLAG_EXTENDED_DEP = 0b00001000;
export const FLAG_NL_PASSTHROUGH = 0x04;
export const FRAGMENT_HEADER_BYTES = 6;
export const LORA_FLOOR_BYTES = 51;
export const LORA_STANDARD_BYTES = 255;
export var LossPolicy;
(function (LossPolicy) {
    LossPolicy["FAIL_SAFE"] = "\u03A6";
    LossPolicy["GRACEFUL_DEGRADATION"] = "\u0393";
    LossPolicy["ATOMIC"] = "\u039B";
})(LossPolicy || (LossPolicy = {}));
export var BAELMode;
(function (BAELMode) {
    BAELMode[BAELMode["FULL_OSMP"] = 0] = "FULL_OSMP";
    BAELMode[BAELMode["TCL_ONLY"] = 2] = "TCL_ONLY";
    BAELMode[BAELMode["NL_PASSTHROUGH"] = 4] = "NL_PASSTHROUGH";
})(BAELMode || (BAELMode = {}));
export var DictUpdateMode;
(function (DictUpdateMode) {
    DictUpdateMode["ADDITIVE"] = "ADDITIVE";
    DictUpdateMode["REPLACE"] = "REPLACE";
    DictUpdateMode["DEPRECATE"] = "DEPRECATE";
})(DictUpdateMode || (DictUpdateMode = {}));
//# sourceMappingURL=types.js.map