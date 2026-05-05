// SPDX-License-Identifier: Apache-2.0
//! eml MDR — 89-macro pre-built EML chain registry.
//!
//! Maps a 1-6 character ASCII shorthand identifier to a [`MacroDefinition`]
//! that describes:
//!
//!   - A list of [`ParametricChain`] templates (the binary structure as a
//!     sequence of `(left, right)` operand pairs over the eml universal
//!     operator `eml(x, y) = exp(x) - ln(y)`).
//!   - The function-class taxonomy (compound arithmetic, NN activation, NN
//!     layer, numerical method, complex arithmetic, linear algebra,
//!     trigonometric, special function, scientific).
//!   - The variant tag (single output, multi output, sender preprocessed,
//!     envelope bounded).
//!   - Optional sender-side preprocessing and receiver-side postprocessing
//!     hooks (transformation op names; params are interpreted by the
//!     evaluator, not stored here).
//!   - Precision class (faithful 1-ULP, correctly-rounded 0-ULP, envelope
//!     bounded).
//!   - Envelope bound spec for envelope-bounded macros.
//!   - Fingerprint membership for cross-SDK reproducibility.
//!
//! The registry is locally-resident on each conformant instrument; no central
//! authority is required at evaluation time. Macros are byte-identical across
//! SDKs by construction: the same 1-6 character shorthand IDs, the same chain
//! templates, and the same evaluation semantics are mirrored in the Python
//! (`osmp.eml_mdr`), Go (`sdk/go/osmp/eml/mdr.go`), and TypeScript
//! (`sdk/typescript/src/eml_mdr.ts`) registries.
//!
//! The registry includes single-output macros (elementary transcendentals and
//! iterated compositions, compound-arithmetic primitives, hyperbolic
//! functions, neural-network activations, layer components, numerical
//! methods, complex arithmetic and small linear algebra, and scientific
//! compounds), multi-output macros (cross product, quaternion multiply,
//! matrix multiply and inverse, softmax3 and log-softmax3, complex multiply
//! Re/Im, attention, LSTM cell, characteristic polynomial, Hadamard),
//! sender-preprocessed macros (sin/cos/atan Taylor on principal-domain
//! inputs, range-reduced sin, sin Chebyshev minimax, erf Taylor), and
//! envelope-bounded macros (RLC resonance, Bernoulli pressure).

/// A parametric chain template.
///
/// Each level is a `(left, right)` operand pair where each operand is one of:
///
///   - `"1"`        — constant `1.0`
///   - `<variable>` — a named input variable (e.g., `"x"`, `"y"`, `"beta"`)
///   - `"fN"`       — output of level N (1-indexed)
#[derive(Debug, Clone, PartialEq)]
pub struct ParametricChain {
    /// Names of the named input variables consumed by this chain.
    pub variables: &'static [&'static str],
    /// Ordered chain levels; each level is a `(left, right)` operand pair.
    pub levels: &'static [(&'static str, &'static str)],
}

/// Function-class taxonomy used to organise macros by mathematical role.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FunctionClass {
    /// Compound arithmetic primitives (negation, sub/add/mul/div, powers, ...).
    CompoundArithmetic,
    /// Neural-network activation functions (sigmoid, ReLU, GELU, ...).
    NnActivation,
    /// Neural-network layer components (dense, attention score, ...).
    NnLayer,
    /// Numerical-method building blocks (interpolation, Newton step, ...).
    NumericalMethod,
    /// Complex-arithmetic primitives (complex multiply Re/Im, magnitude, ...).
    ComplexArithmetic,
    /// Linear-algebra primitives (determinants, traces, matmul, ...).
    LinAlg,
    /// Trigonometric / cyclometric functions (sin, cos, atan, ...).
    Trigonometric,
    /// Special functions (erf, gamma, ...).
    SpecialFunction,
    /// Scientific compounds (Lorentz gamma, blackbody, Doppler, ...).
    Scientific,
}

/// Variant tag for a macro definition.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VariantTag {
    /// Single scalar output; `chain_templates` has length 1.
    SingleOutput,
    /// Multiple output components; `chain_templates` has one entry per output.
    MultiOutput,
    /// Sender-side preprocessing is required before chain evaluation.
    SenderPreprocessed,
    /// Output is bounded only within the documented envelope.
    EnvelopeBounded,
}

/// Precision class characterising the numerical guarantee of a macro.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PrecisionClass {
    /// Faithful rounding within 1 ULP of the true result.
    Faithful1Ulp,
    /// Correctly rounded; result is within 0 ULP of the true result.
    CorrectlyRounded0Ulp,
    /// Output bounded only within the macro's documented envelope.
    EnvelopeBounded,
}

/// Whether a macro participates in the cross-SDK bit-exact fingerprint.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FingerprintMembership {
    /// Contributes to the bit-exact corpus fingerprint across SDKs.
    InBitExactCorpus,
    /// Contributes to a separate envelope-bounded corpus only.
    SeparateEnvelopeCorpus,
    /// Demonstration-only; not part of any cross-SDK fingerprint.
    DemonstrationOnly,
}

/// Envelope characterisation for [`PrecisionClass::EnvelopeBounded`] macros.
#[derive(Debug, Clone, PartialEq)]
pub struct EnvelopeBound {
    /// Numeric bound value (units defined per macro).
    pub bound_value: f64,
    /// Reserved for downstream tooling; empty in the public distribution.
    pub spec_paragraph_ref: &'static str,
    /// Human-readable bound description.
    pub description: &'static str,
}

/// A registered macro.
#[derive(Debug, Clone, PartialEq)]
pub struct MacroDefinition {
    /// 1-6 character ASCII identifier used to reference this macro on the wire.
    pub shorthand_id: &'static str,
    /// Function-class taxonomy.
    pub function_class: FunctionClass,
    /// Variant tag describing single-output / multi-output / preprocessed / envelope.
    pub variant_tag: VariantTag,
    /// One [`ParametricChain`] per output component (length 1 for single-output macros).
    pub chain_templates: &'static [ParametricChain],
    /// Optional sender-side preprocessing operation name.
    pub preprocessing: Option<&'static str>,
    /// Optional receiver-side postprocessing operation name.
    pub postprocessing: Option<&'static str>,
    /// Numerical precision class.
    pub precision_class: PrecisionClass,
    /// Envelope bound spec (populated for envelope-bounded macros).
    pub envelope_bound: Option<EnvelopeBound>,
    /// Reserved for downstream tooling; empty in the public distribution.
    pub patent_claim_refs: &'static [&'static str],
    /// Cross-SDK fingerprint participation.
    pub fingerprint_membership: FingerprintMembership,
    /// Human-readable description.
    pub description: &'static str,
}

/// The 89-macro registry. Order is stable and load-bearing for any tool that
/// hashes the registry as a sequence.
pub static REGISTRY: &[MacroDefinition] = &[
    MacroDefinition {
        shorthand_id: "ABS",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "half"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "x"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "f19"), ("f20", "1"), ("1", "f21"), ("1", "1"), ("f23", "1"), ("1", "f24"), ("1", "half"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("1", "f25"), ("f32", "1"), ("1", "f33"), ("f34", "f22"), ("1", "f28"), ("f36", "1"), ("1", "f37"), ("f35", "1"), ("f38", "f39"), ("f40", "1"), ("f41", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "|x| = sqrt(x^2)",
    },
    MacroDefinition {
        shorthand_id: "ADD",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "y"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("y", "1"), ("f6", "f7"), ("1", "x"), ("f9", "1"), ("1", "f10"), ("f8", "1"), ("f11", "f12")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "x + y",
    },
    MacroDefinition {
        shorthand_id: "ATA",
        function_class: FunctionClass::Trigonometric,
        variant_tag: VariantTag::SenderPreprocessed,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "x"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "x"), ("f23", "1"), ("1", "f24"), ("1", "f19"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "f19"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f38"), ("f42", "1"), ("1", "f43"), ("1", "f19"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "f19"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f57"), ("f61", "1"), ("1", "f62"), ("1", "f19"), ("f64", "1"), ("1", "f65"), ("1", "f60"), ("f67", "1"), ("1", "f68"), ("f69", "f19"), ("1", "f63"), ("f71", "1"), ("1", "f72"), ("f70", "1"), ("f73", "f74"), ("f75", "1"), ("1", "1"), ("f77", "1"), ("1", "f78"), ("1", "f76"), ("f80", "1"), ("1", "f81"), ("1", "f19"), ("f83", "1"), ("1", "f84"), ("1", "f79"), ("f86", "1"), ("1", "f87"), ("f88", "f19"), ("1", "f82"), ("f90", "1"), ("1", "f91"), ("f89", "1"), ("f92", "f93"), ("f94", "1"), ("1", "1"), ("f96", "1"), ("1", "f97"), ("1", "f95"), ("f99", "1"), ("1", "f100"), ("1", "f19"), ("f102", "1"), ("1", "f103"), ("1", "f98"), ("f105", "1"), ("1", "f106"), ("f107", "f19"), ("1", "f101"), ("f109", "1"), ("1", "f110"), ("f108", "1"), ("f111", "f112"), ("f113", "1"), ("1", "1"), ("f115", "1"), ("1", "f116"), ("1", "f114"), ("f118", "1"), ("1", "f119"), ("1", "f19"), ("f121", "1"), ("1", "f122"), ("1", "f117"), ("f124", "1"), ("1", "f125"), ("f126", "f19"), ("1", "f120"), ("f128", "1"), ("1", "f129"), ("f127", "1"), ("f130", "f131"), ("f132", "1"), ("1", "1"), ("f134", "1"), ("1", "f135"), ("1", "f133"), ("f137", "1"), ("1", "f138"), ("1", "f19"), ("f140", "1"), ("1", "f141"), ("1", "f136"), ("f143", "1"), ("1", "f144"), ("f145", "f19"), ("1", "f139"), ("f147", "1"), ("1", "f148"), ("f146", "1"), ("f149", "f150"), ("f151", "1"), ("1", "1"), ("f153", "1"), ("1", "f154"), ("1", "f152"), ("f156", "1"), ("1", "f157"), ("1", "f19"), ("f159", "1"), ("1", "f160"), ("1", "f155"), ("f162", "1"), ("1", "f163"), ("f164", "f19"), ("1", "f158"), ("f166", "1"), ("1", "f167"), ("f165", "1"), ("f168", "f169"), ("f170", "1"), ("1", "x"), ("f172", "1"), ("1", "f173"), ("1", "f174"), ("f175", "1"), ("1", "f176"), ("f177", "1"), ("f178", "1"), ("1", "1"), ("f180", "1"), ("1", "f181"), ("1", "f179"), ("f183", "1"), ("1", "f184"), ("1", "1"), ("f186", "1"), ("1", "f187"), ("1", "f182"), ("f189", "1"), ("1", "f190"), ("f191", "1"), ("1", "f185"), ("f193", "1"), ("1", "f194"), ("f192", "1"), ("f195", "f196"), ("f197", "1"), ("1", "1"), ("f199", "1"), ("1", "f200"), ("1", "f201"), ("f202", "1"), ("1", "f203"), ("f198", "1"), ("f204", "f205"), ("1", "1"), ("f207", "1"), ("1", "f208"), ("f206", "1"), ("f209", "f210"), ("1", "f38"), ("f212", "1"), ("1", "f213"), ("1", "f214"), ("f215", "1"), ("1", "f216"), ("f217", "1"), ("f218", "1"), ("1", "1"), ("f220", "1"), ("1", "f221"), ("1", "f219"), ("f223", "1"), ("1", "f224"), ("1", "1"), ("f226", "1"), ("1", "f227"), ("1", "f222"), ("f229", "1"), ("1", "f230"), ("f231", "1"), ("1", "f225"), ("f233", "1"), ("1", "f234"), ("f232", "1"), ("f235", "f236"), ("f237", "1"), ("1", "1"), ("f239", "1"), ("1", "f240"), ("1", "f241"), ("f242", "1"), ("1", "f243"), ("f238", "1"), ("f244", "f245"), ("1", "f211"), ("f247", "1"), ("1", "f248"), ("f246", "1"), ("f249", "f250"), ("1", "f57"), ("f252", "1"), ("1", "f253"), ("1", "f254"), ("f255", "1"), ("1", "f256"), ("f257", "1"), ("f258", "1"), ("1", "1"), ("f260", "1"), ("1", "f261"), ("1", "f259"), ("f263", "1"), ("1", "f264"), ("1", "1"), ("f266", "1"), ("1", "f267"), ("1", "f262"), ("f269", "1"), ("1", "f270"), ("f271", "1"), ("1", "f265"), ("f273", "1"), ("1", "f274"), ("f272", "1"), ("f275", "f276"), ("f277", "1"), ("1", "1"), ("f279", "1"), ("1", "f280"), ("1", "f281"), ("f282", "1"), ("1", "f283"), ("f278", "1"), ("f284", "f285"), ("1", "f251"), ("f287", "1"), ("1", "f288"), ("f286", "1"), ("f289", "f290"), ("1", "f76"), ("f292", "1"), ("1", "f293"), ("1", "f294"), ("f295", "1"), ("1", "f296"), ("f297", "1"), ("f298", "1"), ("1", "1"), ("f300", "1"), ("1", "f301"), ("1", "f299"), ("f303", "1"), ("1", "f304"), ("1", "1"), ("f306", "1"), ("1", "f307"), ("1", "f302"), ("f309", "1"), ("1", "f310"), ("f311", "1"), ("1", "f305"), ("f313", "1"), ("1", "f314"), ("f312", "1"), ("f315", "f316"), ("f317", "1"), ("1", "1"), ("f319", "1"), ("1", "f320"), ("1", "f321"), ("f322", "1"), ("1", "f323"), ("f318", "1"), ("f324", "f325"), ("1", "f291"), ("f327", "1"), ("1", "f328"), ("f326", "1"), ("f329", "f330"), ("1", "f95"), ("f332", "1"), ("1", "f333"), ("1", "f334"), ("f335", "1"), ("1", "f336"), ("f337", "1"), ("f338", "1"), ("1", "1"), ("f340", "1"), ("1", "f341"), ("1", "f339"), ("f343", "1"), ("1", "f344"), ("1", "1"), ("f346", "1"), ("1", "f347"), ("1", "f342"), ("f349", "1"), ("1", "f350"), ("f351", "1"), ("1", "f345"), ("f353", "1"), ("1", "f354"), ("f352", "1"), ("f355", "f356"), ("f357", "1"), ("1", "1"), ("f359", "1"), ("1", "f360"), ("1", "f361"), ("f362", "1"), ("1", "f363"), ("f358", "1"), ("f364", "f365"), ("1", "f331"), ("f367", "1"), ("1", "f368"), ("f366", "1"), ("f369", "f370"), ("1", "f114"), ("f372", "1"), ("1", "f373"), ("1", "f374"), ("f375", "1"), ("1", "f376"), ("f377", "1"), ("f378", "1"), ("1", "1"), ("f380", "1"), ("1", "f381"), ("1", "f379"), ("f383", "1"), ("1", "f384"), ("1", "1"), ("f386", "1"), ("1", "f387"), ("1", "f382"), ("f389", "1"), ("1", "f390"), ("f391", "1"), ("1", "f385"), ("f393", "1"), ("1", "f394"), ("f392", "1"), ("f395", "f396"), ("f397", "1"), ("1", "1"), ("f399", "1"), ("1", "f400"), ("1", "f401"), ("f402", "1"), ("1", "f403"), ("f398", "1"), ("f404", "f405"), ("1", "f371"), ("f407", "1"), ("1", "f408"), ("f406", "1"), ("f409", "f410"), ("1", "f133"), ("f412", "1"), ("1", "f413"), ("1", "f414"), ("f415", "1"), ("1", "f416"), ("f417", "1"), ("f418", "1"), ("1", "1"), ("f420", "1"), ("1", "f421"), ("1", "f419"), ("f423", "1"), ("1", "f424"), ("1", "1"), ("f426", "1"), ("1", "f427"), ("1", "f422"), ("f429", "1"), ("1", "f430"), ("f431", "1"), ("1", "f425"), ("f433", "1"), ("1", "f434"), ("f432", "1"), ("f435", "f436"), ("f437", "1"), ("1", "1"), ("f439", "1"), ("1", "f440"), ("1", "f441"), ("f442", "1"), ("1", "f443"), ("f438", "1"), ("f444", "f445"), ("1", "f411"), ("f447", "1"), ("1", "f448"), ("f446", "1"), ("f449", "f450"), ("1", "f152"), ("f452", "1"), ("1", "f453"), ("1", "f454"), ("f455", "1"), ("1", "f456"), ("f457", "1"), ("f458", "1"), ("1", "1"), ("f460", "1"), ("1", "f461"), ("1", "f459"), ("f463", "1"), ("1", "f464"), ("1", "1"), ("f466", "1"), ("1", "f467"), ("1", "f462"), ("f469", "1"), ("1", "f470"), ("f471", "1"), ("1", "f465"), ("f473", "1"), ("1", "f474"), ("f472", "1"), ("f475", "f476"), ("f477", "1"), ("1", "1"), ("f479", "1"), ("1", "f480"), ("1", "f481"), ("f482", "1"), ("1", "f483"), ("f478", "1"), ("f484", "f485"), ("1", "f451"), ("f487", "1"), ("1", "f488"), ("f486", "1"), ("f489", "f490"), ("1", "f171"), ("f492", "1"), ("1", "f493"), ("1", "f494"), ("f495", "1"), ("1", "f496"), ("f497", "1"), ("f498", "1"), ("1", "1"), ("f500", "1"), ("1", "f501"), ("1", "f499"), ("f503", "1"), ("1", "f504"), ("1", "1"), ("f506", "1"), ("1", "f507"), ("1", "f502"), ("f509", "1"), ("1", "f510"), ("f511", "1"), ("1", "f505"), ("f513", "1"), ("1", "f514"), ("f512", "1"), ("f515", "f516"), ("f517", "1"), ("1", "1"), ("f519", "1"), ("1", "f520"), ("1", "f521"), ("f522", "1"), ("1", "f523"), ("f518", "1"), ("f524", "f525"), ("1", "f491"), ("f527", "1"), ("1", "f528"), ("f526", "1"), ("f529", "f530")],
        },
    ],
        preprocessing: Some("atan_range_reduce"),
        postprocessing: Some("atan_complement_if_reduced"),
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "atan(x) Taylor (principal-domain)",
    },
    MacroDefinition {
        shorthand_id: "ATM",
        function_class: FunctionClass::NnLayer,
        variant_tag: VariantTag::MultiOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["q", "k1", "k2", "sqrt_d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "q"), ("f4", "1"), ("1", "f5"), ("1", "k1"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "k1"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "f19"), ("f20", "1"), ("1", "f21"), ("1", "f22"), ("f23", "1"), ("1", "f24"), ("f25", "sqrt_d"), ("f26", "1"), ("f27", "1")],
        },
        ParametricChain {
            variables: &["q", "k1", "k2", "sqrt_d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "q"), ("f4", "1"), ("1", "f5"), ("1", "k1"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "k1"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "f19"), ("f20", "1"), ("1", "f21"), ("1", "f22"), ("f23", "1"), ("1", "f24"), ("f25", "sqrt_d"), ("f26", "1"), ("f27", "1"), ("1", "1"), ("f29", "1"), ("1", "f30"), ("1", "q"), ("f32", "1"), ("1", "f33"), ("1", "k2"), ("f35", "1"), ("1", "f36"), ("1", "f31"), ("f38", "1"), ("1", "f39"), ("f40", "k2"), ("1", "f34"), ("f42", "1"), ("1", "f43"), ("f41", "1"), ("f44", "f45"), ("f46", "1"), ("1", "f47"), ("f48", "1"), ("1", "f49"), ("1", "f50"), ("f51", "1"), ("1", "f52"), ("f53", "sqrt_d"), ("f54", "1"), ("f55", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "attention 2-head (score_head1, score_head2)",
    },
    MacroDefinition {
        shorthand_id: "ATN",
        function_class: FunctionClass::NnLayer,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["q", "k", "sqrt_d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "q"), ("f4", "1"), ("1", "f5"), ("1", "k"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "k"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "f19"), ("f20", "1"), ("1", "f21"), ("1", "f22"), ("f23", "1"), ("1", "f24"), ("f25", "sqrt_d"), ("f26", "1"), ("f27", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "attention score = exp(q*k/sqrt(d))",
    },
    MacroDefinition {
        shorthand_id: "BES",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["E", "mu", "kT", "one"],
            levels: &[("1", "E"), ("f1", "1"), ("1", "f2"), ("mu", "1"), ("f3", "f4"), ("1", "f5"), ("f6", "1"), ("1", "f7"), ("1", "f8"), ("f9", "1"), ("1", "f10"), ("f11", "kT"), ("f12", "1"), ("f13", "1"), ("1", "f14"), ("f15", "1"), ("1", "f16"), ("one", "1"), ("f17", "f18"), ("1", "one"), ("f20", "1"), ("1", "f21"), ("1", "f22"), ("f23", "1"), ("1", "f24"), ("f25", "f19"), ("f26", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Bose-Einstein 1/(exp((E-mu)/kT) - 1)",
    },
    MacroDefinition {
        shorthand_id: "BOL",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["E", "kT"],
            levels: &[("1", "E"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("f6", "kT"), ("f7", "1"), ("1", "1"), ("f9", "1"), ("1", "f10"), ("1", "f11"), ("f12", "1"), ("1", "f13"), ("f8", "1"), ("f14", "f15"), ("f16", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Boltzmann factor exp(-E/kT)",
    },
    MacroDefinition {
        shorthand_id: "BRN",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::EnvelopeBounded,
        chain_templates: &[
        ParametricChain {
            variables: &["rho", "v", "h", "g", "P_ref", "half"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "half"), ("f4", "1"), ("1", "f5"), ("1", "rho"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "rho"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "v"), ("f23", "1"), ("1", "f24"), ("1", "v"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "v"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f19"), ("f42", "1"), ("1", "f43"), ("1", "f38"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "f38"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "rho"), ("f61", "1"), ("1", "f62"), ("1", "g"), ("f64", "1"), ("1", "f65"), ("1", "f60"), ("f67", "1"), ("1", "f68"), ("f69", "g"), ("1", "f63"), ("f71", "1"), ("1", "f72"), ("f70", "1"), ("f73", "f74"), ("f75", "1"), ("1", "1"), ("f77", "1"), ("1", "f78"), ("1", "f76"), ("f80", "1"), ("1", "f81"), ("1", "h"), ("f83", "1"), ("1", "f84"), ("1", "f79"), ("f86", "1"), ("1", "f87"), ("f88", "h"), ("1", "f82"), ("f90", "1"), ("1", "f91"), ("f89", "1"), ("f92", "f93"), ("f94", "1"), ("1", "P_ref"), ("f96", "1"), ("1", "f97"), ("f57", "1"), ("f98", "f99"), ("1", "f100"), ("f101", "1"), ("1", "f102"), ("f95", "1"), ("f103", "f104")],
        },
    ],
        preprocessing: Some("rescale_P_ref_to_envelope"),
        postprocessing: None,
        precision_class: PrecisionClass::EnvelopeBounded,
        envelope_bound: Some(EnvelopeBound {
        bound_value: 50.0,
        spec_paragraph_ref: "",
        description: "Bernoulli pressure; M1 sender-preprocessed (P_ref rescaled) AND envelope-limited",
    }),
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::SeparateEnvelopeCorpus,
        description: "Bernoulli pressure (envelope-limited + M1 sender-preprocessed)",
    },
    MacroDefinition {
        shorthand_id: "BWR",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["delta_E", "num", "hwhm_sq"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "delta_E"), ("f4", "1"), ("1", "f5"), ("1", "delta_E"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "delta_E"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "f22"), ("f23", "1"), ("1", "f24"), ("hwhm_sq", "1"), ("f25", "f26"), ("1", "f19"), ("f28", "1"), ("1", "f29"), ("f27", "1"), ("f30", "f31"), ("1", "num"), ("f33", "1"), ("1", "f34"), ("1", "f35"), ("f36", "1"), ("1", "f37"), ("f38", "f32"), ("f39", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Breit-Wigner resonance (sender-preprocessed delta_E)",
    },
    MacroDefinition {
        shorthand_id: "CAB",
        function_class: FunctionClass::ComplexArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a", "b", "half"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a"), ("f4", "1"), ("1", "f5"), ("1", "a"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "a"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b"), ("f23", "1"), ("1", "f24"), ("1", "b"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f41"), ("f42", "1"), ("1", "f43"), ("f38", "1"), ("f44", "f45"), ("1", "f19"), ("f47", "1"), ("1", "f48"), ("f46", "1"), ("f49", "f50"), ("1", "f51"), ("f52", "1"), ("1", "f53"), ("1", "1"), ("f55", "1"), ("1", "f56"), ("1", "half"), ("f58", "1"), ("1", "f59"), ("1", "f54"), ("f61", "1"), ("1", "f62"), ("1", "f57"), ("f64", "1"), ("1", "f65"), ("f66", "f54"), ("1", "f60"), ("f68", "1"), ("1", "f69"), ("f67", "1"), ("f70", "f71"), ("f72", "1"), ("f73", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "complex magnitude sqrt(a^2 + b^2)",
    },
    MacroDefinition {
        shorthand_id: "CBT",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "third"],
            levels: &[("1", "x"), ("f1", "1"), ("1", "f2"), ("1", "1"), ("f4", "1"), ("1", "f5"), ("1", "third"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("1", "f6"), ("f13", "1"), ("1", "f14"), ("f15", "f3"), ("1", "f9"), ("f17", "1"), ("1", "f18"), ("f16", "1"), ("f19", "f20"), ("f21", "1"), ("f22", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "cbrt(x) = x^(1/3) (sender provides third=1/3)",
    },
    MacroDefinition {
        shorthand_id: "CDP",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["f", "v_r", "v_s", "v_wave"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("v_r", "1"), ("f6", "f7"), ("1", "v_wave"), ("f9", "1"), ("1", "f10"), ("f8", "1"), ("f11", "f12"), ("1", "1"), ("f14", "1"), ("1", "f15"), ("1", "f16"), ("f17", "1"), ("1", "f18"), ("v_s", "1"), ("f19", "f20"), ("1", "v_wave"), ("f22", "1"), ("1", "f23"), ("f21", "1"), ("f24", "f25"), ("1", "f13"), ("f27", "1"), ("1", "f28"), ("1", "f29"), ("f30", "1"), ("1", "f31"), ("f32", "f26"), ("f33", "1"), ("1", "1"), ("f35", "1"), ("1", "f36"), ("1", "f"), ("f38", "1"), ("1", "f39"), ("1", "f34"), ("f41", "1"), ("1", "f42"), ("1", "f37"), ("f44", "1"), ("1", "f45"), ("f46", "f34"), ("1", "f40"), ("f48", "1"), ("1", "f49"), ("f47", "1"), ("f50", "f51"), ("f52", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "classical Doppler f * (v_wave + v_r)/(v_wave + v_s)",
    },
    MacroDefinition {
        shorthand_id: "CIM",
        function_class: FunctionClass::ComplexArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a", "b", "c", "d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a"), ("f4", "1"), ("1", "f5"), ("1", "d"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "d"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b"), ("f23", "1"), ("1", "f24"), ("1", "c"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "c"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f41"), ("f42", "1"), ("1", "f43"), ("f38", "1"), ("f44", "f45"), ("1", "f19"), ("f47", "1"), ("1", "f48"), ("f46", "1"), ("f49", "f50")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "complex mul Im part: ad + bc",
    },
    MacroDefinition {
        shorthand_id: "CLB",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["q1", "q2", "r", "k_const"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "r"), ("f4", "1"), ("1", "f5"), ("1", "r"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "r"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "q1"), ("f23", "1"), ("1", "f24"), ("1", "q2"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "q2"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "k_const"), ("f42", "1"), ("1", "f43"), ("1", "f38"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "f38"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "f57"), ("f58", "1"), ("1", "f59"), ("1", "f60"), ("f61", "1"), ("1", "f62"), ("f63", "f19"), ("f64", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Coulomb force k * q1 * q2 / r^2",
    },
    MacroDefinition {
        shorthand_id: "CMP",
        function_class: FunctionClass::LinAlg,
        variant_tag: VariantTag::MultiOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a", "b", "c", "d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a"), ("f4", "1"), ("1", "f5"), ("1", "d"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "d"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b"), ("f23", "1"), ("1", "f24"), ("1", "c"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "c"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42")],
        },
        ParametricChain {
            variables: &["a", "b", "c", "d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a"), ("f4", "1"), ("1", "f5"), ("1", "d"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "d"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b"), ("f23", "1"), ("1", "f24"), ("1", "c"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "c"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42"), ("1", "1"), ("f44", "1"), ("1", "f45"), ("1", "f46"), ("f47", "1"), ("1", "f48"), ("d", "1"), ("f49", "f50"), ("1", "a"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "2x2 characteristic polynomial (det, trace)",
    },
    MacroDefinition {
        shorthand_id: "CMU",
        function_class: FunctionClass::ComplexArithmetic,
        variant_tag: VariantTag::MultiOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a", "b", "c", "d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a"), ("f4", "1"), ("1", "f5"), ("1", "c"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "c"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b"), ("f23", "1"), ("1", "f24"), ("1", "d"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "d"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42")],
        },
        ParametricChain {
            variables: &["a", "b", "c", "d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a"), ("f4", "1"), ("1", "f5"), ("1", "d"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "d"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b"), ("f23", "1"), ("1", "f24"), ("1", "c"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "c"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f41"), ("f42", "1"), ("1", "f43"), ("f38", "1"), ("f44", "f45"), ("1", "f19"), ("f47", "1"), ("1", "f48"), ("f46", "1"), ("f49", "f50")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "complex multiplication (Re, Im) as multi-output pair",
    },
    MacroDefinition {
        shorthand_id: "COS",
        function_class: FunctionClass::Trigonometric,
        variant_tag: VariantTag::SenderPreprocessed,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "x"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "1"), ("f23", "1"), ("1", "f24"), ("1", "f19"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "f19"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f38"), ("f42", "1"), ("1", "f43"), ("1", "f19"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "f19"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f57"), ("f61", "1"), ("1", "f62"), ("1", "f19"), ("f64", "1"), ("1", "f65"), ("1", "f60"), ("f67", "1"), ("1", "f68"), ("f69", "f19"), ("1", "f63"), ("f71", "1"), ("1", "f72"), ("f70", "1"), ("f73", "f74"), ("f75", "1"), ("1", "1"), ("f77", "1"), ("1", "f78"), ("1", "f76"), ("f80", "1"), ("1", "f81"), ("1", "f19"), ("f83", "1"), ("1", "f84"), ("1", "f79"), ("f86", "1"), ("1", "f87"), ("f88", "f19"), ("1", "f82"), ("f90", "1"), ("1", "f91"), ("f89", "1"), ("f92", "f93"), ("f94", "1"), ("1", "1"), ("f96", "1"), ("1", "f97"), ("1", "f95"), ("f99", "1"), ("1", "f100"), ("1", "f19"), ("f102", "1"), ("1", "f103"), ("1", "f98"), ("f105", "1"), ("1", "f106"), ("f107", "f19"), ("1", "f101"), ("f109", "1"), ("1", "f110"), ("f108", "1"), ("f111", "f112"), ("f113", "1"), ("1", "1"), ("f115", "1"), ("1", "f116"), ("1", "f114"), ("f118", "1"), ("1", "f119"), ("1", "f19"), ("f121", "1"), ("1", "f122"), ("1", "f117"), ("f124", "1"), ("1", "f125"), ("f126", "f19"), ("1", "f120"), ("f128", "1"), ("1", "f129"), ("f127", "1"), ("f130", "f131"), ("f132", "1"), ("1", "1"), ("f134", "1"), ("1", "f135"), ("1", "f136"), ("f137", "1"), ("1", "f138"), ("f139", "1"), ("f140", "1"), ("1", "1"), ("f142", "1"), ("1", "f143"), ("1", "f141"), ("f145", "1"), ("1", "f146"), ("1", "1"), ("f148", "1"), ("1", "f149"), ("1", "f144"), ("f151", "1"), ("1", "f152"), ("f153", "1"), ("1", "f147"), ("f155", "1"), ("1", "f156"), ("f154", "1"), ("f157", "f158"), ("f159", "1"), ("1", "1"), ("f161", "1"), ("1", "f162"), ("1", "f163"), ("f164", "1"), ("1", "f165"), ("f160", "1"), ("f166", "f167"), ("1", "1"), ("f169", "1"), ("1", "f170"), ("f168", "1"), ("f171", "f172"), ("1", "f38"), ("f174", "1"), ("1", "f175"), ("1", "f176"), ("f177", "1"), ("1", "f178"), ("f179", "1"), ("f180", "1"), ("1", "1"), ("f182", "1"), ("1", "f183"), ("1", "f181"), ("f185", "1"), ("1", "f186"), ("1", "1"), ("f188", "1"), ("1", "f189"), ("1", "f184"), ("f191", "1"), ("1", "f192"), ("f193", "1"), ("1", "f187"), ("f195", "1"), ("1", "f196"), ("f194", "1"), ("f197", "f198"), ("f199", "1"), ("1", "1"), ("f201", "1"), ("1", "f202"), ("1", "f203"), ("f204", "1"), ("1", "f205"), ("f200", "1"), ("f206", "f207"), ("1", "f173"), ("f209", "1"), ("1", "f210"), ("f208", "1"), ("f211", "f212"), ("1", "f57"), ("f214", "1"), ("1", "f215"), ("1", "f216"), ("f217", "1"), ("1", "f218"), ("f219", "1"), ("f220", "1"), ("1", "1"), ("f222", "1"), ("1", "f223"), ("1", "f221"), ("f225", "1"), ("1", "f226"), ("1", "1"), ("f228", "1"), ("1", "f229"), ("1", "f224"), ("f231", "1"), ("1", "f232"), ("f233", "1"), ("1", "f227"), ("f235", "1"), ("1", "f236"), ("f234", "1"), ("f237", "f238"), ("f239", "1"), ("1", "1"), ("f241", "1"), ("1", "f242"), ("1", "f243"), ("f244", "1"), ("1", "f245"), ("f240", "1"), ("f246", "f247"), ("1", "f213"), ("f249", "1"), ("1", "f250"), ("f248", "1"), ("f251", "f252"), ("1", "f76"), ("f254", "1"), ("1", "f255"), ("1", "f256"), ("f257", "1"), ("1", "f258"), ("f259", "1"), ("f260", "1"), ("1", "1"), ("f262", "1"), ("1", "f263"), ("1", "f261"), ("f265", "1"), ("1", "f266"), ("1", "1"), ("f268", "1"), ("1", "f269"), ("1", "f264"), ("f271", "1"), ("1", "f272"), ("f273", "1"), ("1", "f267"), ("f275", "1"), ("1", "f276"), ("f274", "1"), ("f277", "f278"), ("f279", "1"), ("1", "1"), ("f281", "1"), ("1", "f282"), ("1", "f283"), ("f284", "1"), ("1", "f285"), ("f280", "1"), ("f286", "f287"), ("1", "f253"), ("f289", "1"), ("1", "f290"), ("f288", "1"), ("f291", "f292"), ("1", "f95"), ("f294", "1"), ("1", "f295"), ("1", "f296"), ("f297", "1"), ("1", "f298"), ("f299", "1"), ("f300", "1"), ("1", "1"), ("f302", "1"), ("1", "f303"), ("1", "f301"), ("f305", "1"), ("1", "f306"), ("1", "1"), ("f308", "1"), ("1", "f309"), ("1", "f304"), ("f311", "1"), ("1", "f312"), ("f313", "1"), ("1", "f307"), ("f315", "1"), ("1", "f316"), ("f314", "1"), ("f317", "f318"), ("f319", "1"), ("1", "1"), ("f321", "1"), ("1", "f322"), ("1", "f323"), ("f324", "1"), ("1", "f325"), ("f320", "1"), ("f326", "f327"), ("1", "f293"), ("f329", "1"), ("1", "f330"), ("f328", "1"), ("f331", "f332"), ("1", "f114"), ("f334", "1"), ("1", "f335"), ("1", "f336"), ("f337", "1"), ("1", "f338"), ("f339", "1"), ("f340", "1"), ("1", "1"), ("f342", "1"), ("1", "f343"), ("1", "f341"), ("f345", "1"), ("1", "f346"), ("1", "1"), ("f348", "1"), ("1", "f349"), ("1", "f344"), ("f351", "1"), ("1", "f352"), ("f353", "1"), ("1", "f347"), ("f355", "1"), ("1", "f356"), ("f354", "1"), ("f357", "f358"), ("f359", "1"), ("1", "1"), ("f361", "1"), ("1", "f362"), ("1", "f363"), ("f364", "1"), ("1", "f365"), ("f360", "1"), ("f366", "f367"), ("1", "f333"), ("f369", "1"), ("1", "f370"), ("f368", "1"), ("f371", "f372"), ("1", "f133"), ("f374", "1"), ("1", "f375"), ("1", "f376"), ("f377", "1"), ("1", "f378"), ("f379", "1"), ("f380", "1"), ("1", "1"), ("f382", "1"), ("1", "f383"), ("1", "f381"), ("f385", "1"), ("1", "f386"), ("1", "1"), ("f388", "1"), ("1", "f389"), ("1", "f384"), ("f391", "1"), ("1", "f392"), ("f393", "1"), ("1", "f387"), ("f395", "1"), ("1", "f396"), ("f394", "1"), ("f397", "f398"), ("f399", "1"), ("1", "1"), ("f401", "1"), ("1", "f402"), ("1", "f403"), ("f404", "1"), ("1", "f405"), ("f400", "1"), ("f406", "f407"), ("1", "f373"), ("f409", "1"), ("1", "f410"), ("f408", "1"), ("f411", "f412")],
        },
    ],
        preprocessing: Some("modulo_2pi_with_quadrant"),
        postprocessing: Some("apply_quadrant_sign_for_cos"),
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "cos(x) Taylor (principal-domain)",
    },
    MacroDefinition {
        shorthand_id: "CP3",
        function_class: FunctionClass::LinAlg,
        variant_tag: VariantTag::MultiOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a1", "a2", "a3", "b1", "b2", "b3"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a2"), ("f4", "1"), ("1", "f5"), ("1", "b3"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "b3"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "a3"), ("f23", "1"), ("1", "f24"), ("1", "b2"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b2"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42")],
        },
        ParametricChain {
            variables: &["a1", "a2", "a3", "b1", "b2", "b3"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a2"), ("f4", "1"), ("1", "f5"), ("1", "b3"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "b3"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "a3"), ("f23", "1"), ("1", "f24"), ("1", "b2"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b2"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42"), ("1", "1"), ("f44", "1"), ("1", "f45"), ("1", "a3"), ("f47", "1"), ("1", "f48"), ("1", "b1"), ("f50", "1"), ("1", "f51"), ("1", "f46"), ("f53", "1"), ("1", "f54"), ("f55", "b1"), ("1", "f49"), ("f57", "1"), ("1", "f58"), ("f56", "1"), ("f59", "f60"), ("f61", "1"), ("1", "1"), ("f63", "1"), ("1", "f64"), ("1", "a1"), ("f66", "1"), ("1", "f67"), ("1", "b3"), ("f69", "1"), ("1", "f70"), ("1", "f65"), ("f72", "1"), ("1", "f73"), ("f74", "b3"), ("1", "f68"), ("f76", "1"), ("1", "f77"), ("f75", "1"), ("f78", "f79"), ("f80", "1"), ("1", "f62"), ("f82", "1"), ("1", "f83"), ("f81", "1"), ("f84", "f85")],
        },
        ParametricChain {
            variables: &["a1", "a2", "a3", "b1", "b2", "b3"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a2"), ("f4", "1"), ("1", "f5"), ("1", "b3"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "b3"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "a3"), ("f23", "1"), ("1", "f24"), ("1", "b2"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b2"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42"), ("1", "1"), ("f44", "1"), ("1", "f45"), ("1", "a3"), ("f47", "1"), ("1", "f48"), ("1", "b1"), ("f50", "1"), ("1", "f51"), ("1", "f46"), ("f53", "1"), ("1", "f54"), ("f55", "b1"), ("1", "f49"), ("f57", "1"), ("1", "f58"), ("f56", "1"), ("f59", "f60"), ("f61", "1"), ("1", "1"), ("f63", "1"), ("1", "f64"), ("1", "a1"), ("f66", "1"), ("1", "f67"), ("1", "b3"), ("f69", "1"), ("1", "f70"), ("1", "f65"), ("f72", "1"), ("1", "f73"), ("f74", "b3"), ("1", "f68"), ("f76", "1"), ("1", "f77"), ("f75", "1"), ("f78", "f79"), ("f80", "1"), ("1", "f62"), ("f82", "1"), ("1", "f83"), ("f81", "1"), ("f84", "f85"), ("1", "1"), ("f87", "1"), ("1", "f88"), ("1", "a1"), ("f90", "1"), ("1", "f91"), ("1", "b2"), ("f93", "1"), ("1", "f94"), ("1", "f89"), ("f96", "1"), ("1", "f97"), ("f98", "b2"), ("1", "f92"), ("f100", "1"), ("1", "f101"), ("f99", "1"), ("f102", "f103"), ("f104", "1"), ("1", "1"), ("f106", "1"), ("1", "f107"), ("1", "a2"), ("f109", "1"), ("1", "f110"), ("1", "b1"), ("f112", "1"), ("1", "f113"), ("1", "f108"), ("f115", "1"), ("1", "f116"), ("f117", "b1"), ("1", "f111"), ("f119", "1"), ("1", "f120"), ("f118", "1"), ("f121", "f122"), ("f123", "1"), ("1", "f105"), ("f125", "1"), ("1", "f126"), ("f124", "1"), ("f127", "f128")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "3D cross product",
    },
    MacroDefinition {
        shorthand_id: "CRE",
        function_class: FunctionClass::ComplexArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a", "b", "c", "d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a"), ("f4", "1"), ("1", "f5"), ("1", "c"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "c"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b"), ("f23", "1"), ("1", "f24"), ("1", "d"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "d"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "complex mul Re part: ac - bd",
    },
    MacroDefinition {
        shorthand_id: "CSH",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "half"],
            levels: &[("x", "1"), ("1", "1"), ("f2", "1"), ("1", "f3"), ("1", "f4"), ("f5", "1"), ("1", "f6"), ("x", "1"), ("f7", "f8"), ("f9", "1"), ("1", "1"), ("f11", "1"), ("1", "f12"), ("1", "f13"), ("f14", "1"), ("1", "f15"), ("f10", "1"), ("f16", "f17"), ("1", "f1"), ("f19", "1"), ("1", "f20"), ("f18", "1"), ("f21", "f22"), ("1", "1"), ("f24", "1"), ("1", "f25"), ("1", "f23"), ("f27", "1"), ("1", "f28"), ("1", "half"), ("f30", "1"), ("1", "f31"), ("1", "f26"), ("f33", "1"), ("1", "f34"), ("f35", "half"), ("1", "f29"), ("f37", "1"), ("1", "f38"), ("f36", "1"), ("f39", "f40"), ("f41", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "cosh(x)",
    },
    MacroDefinition {
        shorthand_id: "CUB",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "x"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "x"), ("f23", "1"), ("1", "f24"), ("1", "f19"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "f19"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "x^3",
    },
    MacroDefinition {
        shorthand_id: "DEN",
        function_class: FunctionClass::NnLayer,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["w", "x", "b"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "w"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "f22"), ("f23", "1"), ("1", "f24"), ("b", "1"), ("f25", "f26"), ("1", "f19"), ("f28", "1"), ("1", "f29"), ("f27", "1"), ("f30", "f31")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "dense forward scalar (no activation): w*x + b",
    },
    MacroDefinition {
        shorthand_id: "DIV",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "y"],
            levels: &[("1", "x"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("f6", "y"), ("f7", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "x / y (= eml(ln(x), y))",
    },
    MacroDefinition {
        shorthand_id: "DOP",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["f", "beta", "one"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("beta", "1"), ("f6", "f7"), ("1", "one"), ("f9", "1"), ("1", "f10"), ("f8", "1"), ("f11", "f12"), ("1", "one"), ("f14", "1"), ("1", "f15"), ("beta", "1"), ("f16", "f17"), ("1", "f13"), ("f19", "1"), ("1", "f20"), ("1", "f21"), ("f22", "1"), ("1", "f23"), ("f24", "f18"), ("f25", "1"), ("1", "f26"), ("f27", "1"), ("1", "f28"), ("1", "1"), ("f30", "1"), ("1", "f31"), ("1", "1"), ("f33", "1"), ("1", "f34"), ("1", "f29"), ("f36", "1"), ("1", "f37"), ("1", "f32"), ("f39", "1"), ("1", "f40"), ("f41", "f29"), ("1", "f35"), ("f43", "1"), ("1", "f44"), ("f42", "1"), ("f45", "f46"), ("f47", "1"), ("f48", "1"), ("1", "1"), ("f50", "1"), ("1", "f51"), ("1", "f"), ("f53", "1"), ("1", "f54"), ("1", "f49"), ("f56", "1"), ("1", "f57"), ("1", "f52"), ("f59", "1"), ("1", "f60"), ("f61", "f49"), ("1", "f55"), ("f63", "1"), ("1", "f64"), ("f62", "1"), ("f65", "f66"), ("f67", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Relativistic Doppler shift",
    },
    MacroDefinition {
        shorthand_id: "DT2",
        function_class: FunctionClass::LinAlg,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a", "b", "c", "d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a"), ("f4", "1"), ("1", "f5"), ("1", "d"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "d"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b"), ("f23", "1"), ("1", "f24"), ("1", "c"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "c"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "2x2 determinant ad - bc",
    },
    MacroDefinition {
        shorthand_id: "EE2",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("x", "1"), ("f1", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "exp(exp(x))",
    },
    MacroDefinition {
        shorthand_id: "EE3",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("x", "1"), ("f1", "1"), ("f2", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "exp(exp(exp(x)))",
    },
    MacroDefinition {
        shorthand_id: "EE4",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("x", "1"), ("f1", "1"), ("f2", "1"), ("f3", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "exp^4(x)",
    },
    MacroDefinition {
        shorthand_id: "EE5",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("x", "1"), ("f1", "1"), ("f2", "1"), ("f3", "1"), ("f4", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "exp^5(x)",
    },
    MacroDefinition {
        shorthand_id: "EEM",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("x", "1"), ("f1", "1"), ("1", "f2")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "e - exp(x)",
    },
    MacroDefinition {
        shorthand_id: "EEX",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "x"), ("f1", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "e^e / x",
    },
    MacroDefinition {
        shorthand_id: "ELN",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("x", "x")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "exp(x) - ln(x)",
    },
    MacroDefinition {
        shorthand_id: "ELU",
        function_class: FunctionClass::NnActivation,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "alpha", "k", "half"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "k"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "f22"), ("f23", "1"), ("1", "f24"), ("f19", "1"), ("f25", "f26"), ("f27", "1"), ("1", "1"), ("f29", "1"), ("1", "f30"), ("1", "f31"), ("f32", "1"), ("1", "f33"), ("f28", "1"), ("f34", "f35"), ("1", "1"), ("f37", "1"), ("1", "f38"), ("f36", "1"), ("f39", "f40"), ("1", "1"), ("f42", "1"), ("1", "f43"), ("1", "f44"), ("f45", "1"), ("1", "f46"), ("f47", "f41"), ("f48", "1"), ("1", "1"), ("f50", "1"), ("1", "f51"), ("f49", "1"), ("f52", "f53"), ("x", "1"), ("1", "f55"), ("f56", "1"), ("1", "f57"), ("1", "1"), ("f58", "f59"), ("1", "1"), ("f61", "1"), ("1", "f62"), ("1", "alpha"), ("f64", "1"), ("1", "f65"), ("1", "f60"), ("f67", "1"), ("1", "f68"), ("1", "f63"), ("f70", "1"), ("1", "f71"), ("f72", "f60"), ("1", "f66"), ("f74", "1"), ("1", "f75"), ("f73", "1"), ("f76", "f77"), ("f78", "1"), ("1", "1"), ("f80", "1"), ("1", "f81"), ("1", "f49"), ("f83", "1"), ("1", "f84"), ("1", "x"), ("f86", "1"), ("1", "f87"), ("1", "f82"), ("f89", "1"), ("1", "f90"), ("f91", "x"), ("1", "f85"), ("f93", "1"), ("1", "f94"), ("f92", "1"), ("f95", "f96"), ("f97", "1"), ("1", "1"), ("f99", "1"), ("1", "f100"), ("1", "f54"), ("f102", "1"), ("1", "f103"), ("1", "f79"), ("f105", "1"), ("1", "f106"), ("1", "f101"), ("f108", "1"), ("1", "f109"), ("f110", "f79"), ("1", "f104"), ("f112", "1"), ("1", "f113"), ("f111", "1"), ("f114", "f115"), ("f116", "1"), ("1", "1"), ("f118", "1"), ("1", "f119"), ("1", "f120"), ("f121", "1"), ("1", "f122"), ("f117", "1"), ("f123", "f124"), ("1", "f98"), ("f126", "1"), ("1", "f127"), ("f125", "1"), ("f128", "f129")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "ELU (smooth approx, k controls switch sharpness)",
    },
    MacroDefinition {
        shorthand_id: "EM1",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("x", "f1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "exp(x) - 1",
    },
    MacroDefinition {
        shorthand_id: "EME",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("x", "f2")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "exp(x) - e",
    },
    MacroDefinition {
        shorthand_id: "EMX",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("x", "1"), ("x", "f1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "exp(x) - x",
    },
    MacroDefinition {
        shorthand_id: "EOX",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("f3", "x"), ("f4", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "e/x",
    },
    MacroDefinition {
        shorthand_id: "ERF",
        function_class: FunctionClass::SpecialFunction,
        variant_tag: VariantTag::SenderPreprocessed,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "x"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "x"), ("f23", "1"), ("1", "f24"), ("1", "f19"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "f19"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f38"), ("f42", "1"), ("1", "f43"), ("1", "f19"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "f19"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f57"), ("f61", "1"), ("1", "f62"), ("1", "f19"), ("f64", "1"), ("1", "f65"), ("1", "f60"), ("f67", "1"), ("1", "f68"), ("f69", "f19"), ("1", "f63"), ("f71", "1"), ("1", "f72"), ("f70", "1"), ("f73", "f74"), ("f75", "1"), ("1", "1"), ("f77", "1"), ("1", "f78"), ("1", "f76"), ("f80", "1"), ("1", "f81"), ("1", "f19"), ("f83", "1"), ("1", "f84"), ("1", "f79"), ("f86", "1"), ("1", "f87"), ("f88", "f19"), ("1", "f82"), ("f90", "1"), ("1", "f91"), ("f89", "1"), ("f92", "f93"), ("f94", "1"), ("1", "1"), ("f96", "1"), ("1", "f97"), ("1", "f95"), ("f99", "1"), ("1", "f100"), ("1", "f19"), ("f102", "1"), ("1", "f103"), ("1", "f98"), ("f105", "1"), ("1", "f106"), ("f107", "f19"), ("1", "f101"), ("f109", "1"), ("1", "f110"), ("f108", "1"), ("f111", "f112"), ("f113", "1"), ("1", "1"), ("f115", "1"), ("1", "f116"), ("1", "f114"), ("f118", "1"), ("1", "f119"), ("1", "f19"), ("f121", "1"), ("1", "f122"), ("1", "f117"), ("f124", "1"), ("1", "f125"), ("f126", "f19"), ("1", "f120"), ("f128", "1"), ("1", "f129"), ("f127", "1"), ("f130", "f131"), ("f132", "1"), ("1", "x"), ("f134", "1"), ("1", "f135"), ("1", "f136"), ("f137", "1"), ("1", "f138"), ("f139", "1"), ("f140", "1"), ("1", "1"), ("f142", "1"), ("1", "f143"), ("1", "f141"), ("f145", "1"), ("1", "f146"), ("1", "1"), ("f148", "1"), ("1", "f149"), ("1", "f144"), ("f151", "1"), ("1", "f152"), ("f153", "1"), ("1", "f147"), ("f155", "1"), ("1", "f156"), ("f154", "1"), ("f157", "f158"), ("f159", "1"), ("1", "1"), ("f161", "1"), ("1", "f162"), ("1", "f163"), ("f164", "1"), ("1", "f165"), ("f160", "1"), ("f166", "f167"), ("1", "1"), ("f169", "1"), ("1", "f170"), ("f168", "1"), ("f171", "f172"), ("1", "f38"), ("f174", "1"), ("1", "f175"), ("1", "f176"), ("f177", "1"), ("1", "f178"), ("f179", "1"), ("f180", "1"), ("1", "1"), ("f182", "1"), ("1", "f183"), ("1", "f181"), ("f185", "1"), ("1", "f186"), ("1", "1"), ("f188", "1"), ("1", "f189"), ("1", "f184"), ("f191", "1"), ("1", "f192"), ("f193", "1"), ("1", "f187"), ("f195", "1"), ("1", "f196"), ("f194", "1"), ("f197", "f198"), ("f199", "1"), ("1", "1"), ("f201", "1"), ("1", "f202"), ("1", "f203"), ("f204", "1"), ("1", "f205"), ("f200", "1"), ("f206", "f207"), ("1", "f173"), ("f209", "1"), ("1", "f210"), ("f208", "1"), ("f211", "f212"), ("1", "f57"), ("f214", "1"), ("1", "f215"), ("1", "f216"), ("f217", "1"), ("1", "f218"), ("f219", "1"), ("f220", "1"), ("1", "1"), ("f222", "1"), ("1", "f223"), ("1", "f221"), ("f225", "1"), ("1", "f226"), ("1", "1"), ("f228", "1"), ("1", "f229"), ("1", "f224"), ("f231", "1"), ("1", "f232"), ("f233", "1"), ("1", "f227"), ("f235", "1"), ("1", "f236"), ("f234", "1"), ("f237", "f238"), ("f239", "1"), ("1", "1"), ("f241", "1"), ("1", "f242"), ("1", "f243"), ("f244", "1"), ("1", "f245"), ("f240", "1"), ("f246", "f247"), ("1", "f213"), ("f249", "1"), ("1", "f250"), ("f248", "1"), ("f251", "f252"), ("1", "f76"), ("f254", "1"), ("1", "f255"), ("1", "f256"), ("f257", "1"), ("1", "f258"), ("f259", "1"), ("f260", "1"), ("1", "1"), ("f262", "1"), ("1", "f263"), ("1", "f261"), ("f265", "1"), ("1", "f266"), ("1", "1"), ("f268", "1"), ("1", "f269"), ("1", "f264"), ("f271", "1"), ("1", "f272"), ("f273", "1"), ("1", "f267"), ("f275", "1"), ("1", "f276"), ("f274", "1"), ("f277", "f278"), ("f279", "1"), ("1", "1"), ("f281", "1"), ("1", "f282"), ("1", "f283"), ("f284", "1"), ("1", "f285"), ("f280", "1"), ("f286", "f287"), ("1", "f253"), ("f289", "1"), ("1", "f290"), ("f288", "1"), ("f291", "f292"), ("1", "f95"), ("f294", "1"), ("1", "f295"), ("1", "f296"), ("f297", "1"), ("1", "f298"), ("f299", "1"), ("f300", "1"), ("1", "1"), ("f302", "1"), ("1", "f303"), ("1", "f301"), ("f305", "1"), ("1", "f306"), ("1", "1"), ("f308", "1"), ("1", "f309"), ("1", "f304"), ("f311", "1"), ("1", "f312"), ("f313", "1"), ("1", "f307"), ("f315", "1"), ("1", "f316"), ("f314", "1"), ("f317", "f318"), ("f319", "1"), ("1", "1"), ("f321", "1"), ("1", "f322"), ("1", "f323"), ("f324", "1"), ("1", "f325"), ("f320", "1"), ("f326", "f327"), ("1", "f293"), ("f329", "1"), ("1", "f330"), ("f328", "1"), ("f331", "f332"), ("1", "f114"), ("f334", "1"), ("1", "f335"), ("1", "f336"), ("f337", "1"), ("1", "f338"), ("f339", "1"), ("f340", "1"), ("1", "1"), ("f342", "1"), ("1", "f343"), ("1", "f341"), ("f345", "1"), ("1", "f346"), ("1", "1"), ("f348", "1"), ("1", "f349"), ("1", "f344"), ("f351", "1"), ("1", "f352"), ("f353", "1"), ("1", "f347"), ("f355", "1"), ("1", "f356"), ("f354", "1"), ("f357", "f358"), ("f359", "1"), ("1", "1"), ("f361", "1"), ("1", "f362"), ("1", "f363"), ("f364", "1"), ("1", "f365"), ("f360", "1"), ("f366", "f367"), ("1", "f333"), ("f369", "1"), ("1", "f370"), ("f368", "1"), ("f371", "f372"), ("1", "f133"), ("f374", "1"), ("1", "f375"), ("1", "f376"), ("f377", "1"), ("1", "f378"), ("f379", "1"), ("f380", "1"), ("1", "1"), ("f382", "1"), ("1", "f383"), ("1", "f381"), ("f385", "1"), ("1", "f386"), ("1", "1"), ("f388", "1"), ("1", "f389"), ("1", "f384"), ("f391", "1"), ("1", "f392"), ("f393", "1"), ("1", "f387"), ("f395", "1"), ("1", "f396"), ("f394", "1"), ("f397", "f398"), ("f399", "1"), ("1", "1"), ("f401", "1"), ("1", "f402"), ("1", "f403"), ("f404", "1"), ("1", "f405"), ("f400", "1"), ("f406", "f407"), ("1", "f373"), ("f409", "1"), ("1", "f410"), ("f408", "1"), ("f411", "f412"), ("1", "1"), ("f414", "1"), ("1", "f415"), ("1", "1"), ("f417", "1"), ("1", "f418"), ("1", "f413"), ("f420", "1"), ("1", "f421"), ("1", "f416"), ("f423", "1"), ("1", "f424"), ("f425", "f413"), ("1", "f419"), ("f427", "1"), ("1", "f428"), ("f426", "1"), ("f429", "f430"), ("f431", "1")],
        },
    ],
        preprocessing: Some("abs_clamp_to"),
        postprocessing: Some("restore_sign"),
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "erf(x) Taylor (sender-bounded |x|<=1.5)",
    },
    MacroDefinition {
        shorthand_id: "ESX",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("x", "1"), ("1", "f1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "e - x",
    },
    MacroDefinition {
        shorthand_id: "EXP",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("x", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "exp(x) = eml(x, 1)",
    },
    MacroDefinition {
        shorthand_id: "FDR",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["E", "mu", "kT", "one"],
            levels: &[("1", "E"), ("f1", "1"), ("1", "f2"), ("mu", "1"), ("f3", "f4"), ("1", "f5"), ("f6", "1"), ("1", "f7"), ("1", "f8"), ("f9", "1"), ("1", "f10"), ("f11", "kT"), ("f12", "1"), ("f13", "1"), ("1", "1"), ("f15", "1"), ("1", "f16"), ("1", "f17"), ("f18", "1"), ("1", "f19"), ("one", "1"), ("f20", "f21"), ("1", "f14"), ("f23", "1"), ("1", "f24"), ("f22", "1"), ("f25", "f26"), ("1", "one"), ("f28", "1"), ("1", "f29"), ("1", "f30"), ("f31", "1"), ("1", "f32"), ("f33", "f27"), ("f34", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Fermi-Dirac 1/(exp((E-mu)/kT) + 1)",
    },
    MacroDefinition {
        shorthand_id: "FRD",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["z", "H0_sq", "om", "ol", "orad", "ok"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("z", "1"), ("f6", "f7"), ("1", "1"), ("f9", "1"), ("1", "f10"), ("f8", "1"), ("f11", "f12"), ("1", "1"), ("f14", "1"), ("1", "f15"), ("1", "f13"), ("f17", "1"), ("1", "f18"), ("1", "f13"), ("f20", "1"), ("1", "f21"), ("1", "f16"), ("f23", "1"), ("1", "f24"), ("f25", "f13"), ("1", "f19"), ("f27", "1"), ("1", "f28"), ("f26", "1"), ("f29", "f30"), ("f31", "1"), ("1", "1"), ("f33", "1"), ("1", "f34"), ("1", "f32"), ("f36", "1"), ("1", "f37"), ("1", "f13"), ("f39", "1"), ("1", "f40"), ("1", "f35"), ("f42", "1"), ("1", "f43"), ("f44", "f13"), ("1", "f38"), ("f46", "1"), ("1", "f47"), ("f45", "1"), ("f48", "f49"), ("f50", "1"), ("1", "1"), ("f52", "1"), ("1", "f53"), ("1", "f32"), ("f55", "1"), ("1", "f56"), ("1", "f32"), ("f58", "1"), ("1", "f59"), ("1", "f54"), ("f61", "1"), ("1", "f62"), ("f63", "f32"), ("1", "f57"), ("f65", "1"), ("1", "f66"), ("f64", "1"), ("f67", "f68"), ("f69", "1"), ("1", "1"), ("f71", "1"), ("1", "f72"), ("1", "om"), ("f74", "1"), ("1", "f75"), ("1", "f51"), ("f77", "1"), ("1", "f78"), ("1", "f73"), ("f80", "1"), ("1", "f81"), ("f82", "f51"), ("1", "f76"), ("f84", "1"), ("1", "f85"), ("f83", "1"), ("f86", "f87"), ("f88", "1"), ("1", "1"), ("f90", "1"), ("1", "f91"), ("1", "f92"), ("f93", "1"), ("1", "f94"), ("ol", "1"), ("f95", "f96"), ("1", "f89"), ("f98", "1"), ("1", "f99"), ("f97", "1"), ("f100", "f101"), ("1", "1"), ("f103", "1"), ("1", "f104"), ("1", "ok"), ("f106", "1"), ("1", "f107"), ("1", "f32"), ("f109", "1"), ("1", "f110"), ("1", "f105"), ("f112", "1"), ("1", "f113"), ("f114", "f32"), ("1", "f108"), ("f116", "1"), ("1", "f117"), ("f115", "1"), ("f118", "f119"), ("f120", "1"), ("1", "1"), ("f122", "1"), ("1", "f123"), ("1", "f124"), ("f125", "1"), ("1", "f126"), ("f121", "1"), ("f127", "f128"), ("1", "f102"), ("f130", "1"), ("1", "f131"), ("f129", "1"), ("f132", "f133"), ("1", "1"), ("f135", "1"), ("1", "f136"), ("1", "orad"), ("f138", "1"), ("1", "f139"), ("1", "f70"), ("f141", "1"), ("1", "f142"), ("1", "f137"), ("f144", "1"), ("1", "f145"), ("f146", "f70"), ("1", "f140"), ("f148", "1"), ("1", "f149"), ("f147", "1"), ("f150", "f151"), ("f152", "1"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "f156"), ("f157", "1"), ("1", "f158"), ("f153", "1"), ("f159", "f160"), ("1", "f134"), ("f162", "1"), ("1", "f163"), ("f161", "1"), ("f164", "f165"), ("1", "1"), ("f167", "1"), ("1", "f168"), ("1", "H0_sq"), ("f170", "1"), ("1", "f171"), ("1", "f166"), ("f173", "1"), ("1", "f174"), ("1", "f169"), ("f176", "1"), ("1", "f177"), ("f178", "f166"), ("1", "f172"), ("f180", "1"), ("1", "f181"), ("f179", "1"), ("f182", "f183"), ("f184", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Friedmann H^2(z)",
    },
    MacroDefinition {
        shorthand_id: "GLU",
        function_class: FunctionClass::NnActivation,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "coef"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "coef"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "f22"), ("f23", "1"), ("1", "f24"), ("f19", "1"), ("f25", "f26"), ("f27", "1"), ("1", "1"), ("f29", "1"), ("1", "f30"), ("1", "f31"), ("f32", "1"), ("1", "f33"), ("f28", "1"), ("f34", "f35"), ("1", "1"), ("f37", "1"), ("1", "f38"), ("f36", "1"), ("f39", "f40"), ("1", "1"), ("f42", "1"), ("1", "f43"), ("1", "f44"), ("f45", "1"), ("1", "f46"), ("f47", "f41"), ("f48", "1"), ("1", "1"), ("f50", "1"), ("1", "f51"), ("1", "x"), ("f53", "1"), ("1", "f54"), ("1", "f49"), ("f56", "1"), ("1", "f57"), ("1", "f52"), ("f59", "1"), ("1", "f60"), ("f61", "f49"), ("1", "f55"), ("f63", "1"), ("1", "f64"), ("f62", "1"), ("f65", "f66"), ("f67", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "GELU approx (x * sigmoid(coef*x))",
    },
    MacroDefinition {
        shorthand_id: "HAD",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::MultiOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["alpha_re", "alpha_im", "beta_re", "beta_im", "inv_sqrt_2"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("beta_re", "1"), ("f6", "f7"), ("1", "alpha_re"), ("f9", "1"), ("1", "f10"), ("f8", "1"), ("f11", "f12"), ("1", "1"), ("f14", "1"), ("1", "f15"), ("1", "f13"), ("f17", "1"), ("1", "f18"), ("1", "inv_sqrt_2"), ("f20", "1"), ("1", "f21"), ("1", "f16"), ("f23", "1"), ("1", "f24"), ("f25", "inv_sqrt_2"), ("1", "f19"), ("f27", "1"), ("1", "f28"), ("f26", "1"), ("f29", "f30"), ("f31", "1")],
        },
        ParametricChain {
            variables: &["alpha_re", "alpha_im", "beta_re", "beta_im", "inv_sqrt_2"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("beta_re", "1"), ("f6", "f7"), ("1", "alpha_re"), ("f9", "1"), ("1", "f10"), ("f8", "1"), ("f11", "f12"), ("1", "1"), ("f14", "1"), ("1", "f15"), ("1", "f13"), ("f17", "1"), ("1", "f18"), ("1", "inv_sqrt_2"), ("f20", "1"), ("1", "f21"), ("1", "f16"), ("f23", "1"), ("1", "f24"), ("f25", "inv_sqrt_2"), ("1", "f19"), ("f27", "1"), ("1", "f28"), ("f26", "1"), ("f29", "f30"), ("f31", "1"), ("1", "1"), ("f33", "1"), ("1", "f34"), ("1", "f35"), ("f36", "1"), ("1", "f37"), ("beta_im", "1"), ("f38", "f39"), ("1", "alpha_im"), ("f41", "1"), ("1", "f42"), ("f40", "1"), ("f43", "f44"), ("1", "1"), ("f46", "1"), ("1", "f47"), ("1", "f45"), ("f49", "1"), ("1", "f50"), ("1", "inv_sqrt_2"), ("f52", "1"), ("1", "f53"), ("1", "f48"), ("f55", "1"), ("1", "f56"), ("f57", "inv_sqrt_2"), ("1", "f51"), ("f59", "1"), ("1", "f60"), ("f58", "1"), ("f61", "f62"), ("f63", "1")],
        },
        ParametricChain {
            variables: &["alpha_re", "alpha_im", "beta_re", "beta_im", "inv_sqrt_2"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("beta_re", "1"), ("f6", "f7"), ("1", "alpha_re"), ("f9", "1"), ("1", "f10"), ("f8", "1"), ("f11", "f12"), ("1", "1"), ("f14", "1"), ("1", "f15"), ("1", "f13"), ("f17", "1"), ("1", "f18"), ("1", "inv_sqrt_2"), ("f20", "1"), ("1", "f21"), ("1", "f16"), ("f23", "1"), ("1", "f24"), ("f25", "inv_sqrt_2"), ("1", "f19"), ("f27", "1"), ("1", "f28"), ("f26", "1"), ("f29", "f30"), ("f31", "1"), ("1", "1"), ("f33", "1"), ("1", "f34"), ("1", "f35"), ("f36", "1"), ("1", "f37"), ("beta_im", "1"), ("f38", "f39"), ("1", "alpha_im"), ("f41", "1"), ("1", "f42"), ("f40", "1"), ("f43", "f44"), ("1", "1"), ("f46", "1"), ("1", "f47"), ("1", "f45"), ("f49", "1"), ("1", "f50"), ("1", "inv_sqrt_2"), ("f52", "1"), ("1", "f53"), ("1", "f48"), ("f55", "1"), ("1", "f56"), ("f57", "inv_sqrt_2"), ("1", "f51"), ("f59", "1"), ("1", "f60"), ("f58", "1"), ("f61", "f62"), ("f63", "1"), ("1", "alpha_re"), ("f65", "1"), ("1", "f66"), ("beta_re", "1"), ("f67", "f68"), ("1", "1"), ("f70", "1"), ("1", "f71"), ("1", "f69"), ("f73", "1"), ("1", "f74"), ("1", "inv_sqrt_2"), ("f76", "1"), ("1", "f77"), ("1", "f72"), ("f79", "1"), ("1", "f80"), ("f81", "inv_sqrt_2"), ("1", "f75"), ("f83", "1"), ("1", "f84"), ("f82", "1"), ("f85", "f86"), ("f87", "1")],
        },
        ParametricChain {
            variables: &["alpha_re", "alpha_im", "beta_re", "beta_im", "inv_sqrt_2"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("beta_re", "1"), ("f6", "f7"), ("1", "alpha_re"), ("f9", "1"), ("1", "f10"), ("f8", "1"), ("f11", "f12"), ("1", "1"), ("f14", "1"), ("1", "f15"), ("1", "f13"), ("f17", "1"), ("1", "f18"), ("1", "inv_sqrt_2"), ("f20", "1"), ("1", "f21"), ("1", "f16"), ("f23", "1"), ("1", "f24"), ("f25", "inv_sqrt_2"), ("1", "f19"), ("f27", "1"), ("1", "f28"), ("f26", "1"), ("f29", "f30"), ("f31", "1"), ("1", "1"), ("f33", "1"), ("1", "f34"), ("1", "f35"), ("f36", "1"), ("1", "f37"), ("beta_im", "1"), ("f38", "f39"), ("1", "alpha_im"), ("f41", "1"), ("1", "f42"), ("f40", "1"), ("f43", "f44"), ("1", "1"), ("f46", "1"), ("1", "f47"), ("1", "f45"), ("f49", "1"), ("1", "f50"), ("1", "inv_sqrt_2"), ("f52", "1"), ("1", "f53"), ("1", "f48"), ("f55", "1"), ("1", "f56"), ("f57", "inv_sqrt_2"), ("1", "f51"), ("f59", "1"), ("1", "f60"), ("f58", "1"), ("f61", "f62"), ("f63", "1"), ("1", "alpha_re"), ("f65", "1"), ("1", "f66"), ("beta_re", "1"), ("f67", "f68"), ("1", "1"), ("f70", "1"), ("1", "f71"), ("1", "f69"), ("f73", "1"), ("1", "f74"), ("1", "inv_sqrt_2"), ("f76", "1"), ("1", "f77"), ("1", "f72"), ("f79", "1"), ("1", "f80"), ("f81", "inv_sqrt_2"), ("1", "f75"), ("f83", "1"), ("1", "f84"), ("f82", "1"), ("f85", "f86"), ("f87", "1"), ("1", "alpha_im"), ("f89", "1"), ("1", "f90"), ("beta_im", "1"), ("f91", "f92"), ("1", "1"), ("f94", "1"), ("1", "f95"), ("1", "f93"), ("f97", "1"), ("1", "f98"), ("1", "inv_sqrt_2"), ("f100", "1"), ("1", "f101"), ("1", "f96"), ("f103", "1"), ("1", "f104"), ("f105", "inv_sqrt_2"), ("1", "f99"), ("f107", "1"), ("1", "f108"), ("f106", "1"), ("f109", "f110"), ("f111", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::EnvelopeBounded,
        envelope_bound: Some(EnvelopeBound {
        bound_value: 0.00015,
        spec_paragraph_ref: "",
        description: "Hadamard amplitude transformation; envelope-limited at approximately 1.5e-4 for full-state amplitude transformation",
    }),
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::SeparateEnvelopeCorpus,
        description: "Hadamard quantum gate (envelope-bounded)",
    },
    MacroDefinition {
        shorthand_id: "IDN",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "x"), ("f1", "1"), ("1", "f2"), ("f3", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "identity(x)",
    },
    MacroDefinition {
        shorthand_id: "INV",
        function_class: FunctionClass::LinAlg,
        variant_tag: VariantTag::MultiOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a", "b", "c", "d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a"), ("f4", "1"), ("1", "f5"), ("1", "d"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "d"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b"), ("f23", "1"), ("1", "f24"), ("1", "c"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "c"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42"), ("1", "1"), ("f44", "1"), ("1", "f45"), ("1", "f46"), ("f47", "1"), ("1", "f48"), ("f49", "f43"), ("f50", "1"), ("1", "1"), ("f52", "1"), ("1", "f53"), ("1", "f54"), ("f55", "1"), ("1", "f56"), ("b", "1"), ("f57", "f58"), ("1", "1"), ("f60", "1"), ("1", "f61"), ("1", "f62"), ("f63", "1"), ("1", "f64"), ("c", "1"), ("f65", "f66"), ("1", "1"), ("f68", "1"), ("1", "f69"), ("1", "f51"), ("f71", "1"), ("1", "f72"), ("1", "d"), ("f74", "1"), ("1", "f75"), ("1", "f70"), ("f77", "1"), ("1", "f78"), ("f79", "d"), ("1", "f73"), ("f81", "1"), ("1", "f82"), ("f80", "1"), ("f83", "f84"), ("f85", "1")],
        },
        ParametricChain {
            variables: &["a", "b", "c", "d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a"), ("f4", "1"), ("1", "f5"), ("1", "d"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "d"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b"), ("f23", "1"), ("1", "f24"), ("1", "c"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "c"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42"), ("1", "1"), ("f44", "1"), ("1", "f45"), ("1", "f46"), ("f47", "1"), ("1", "f48"), ("f49", "f43"), ("f50", "1"), ("1", "1"), ("f52", "1"), ("1", "f53"), ("1", "f54"), ("f55", "1"), ("1", "f56"), ("b", "1"), ("f57", "f58"), ("1", "1"), ("f60", "1"), ("1", "f61"), ("1", "f62"), ("f63", "1"), ("1", "f64"), ("c", "1"), ("f65", "f66"), ("1", "1"), ("f68", "1"), ("1", "f69"), ("1", "f51"), ("f71", "1"), ("1", "f72"), ("1", "d"), ("f74", "1"), ("1", "f75"), ("1", "f70"), ("f77", "1"), ("1", "f78"), ("f79", "d"), ("1", "f73"), ("f81", "1"), ("1", "f82"), ("f80", "1"), ("f83", "f84"), ("f85", "1"), ("1", "1"), ("f87", "1"), ("1", "f88"), ("1", "f51"), ("f90", "1"), ("1", "f91"), ("1", "f59"), ("f93", "1"), ("1", "f94"), ("1", "f89"), ("f96", "1"), ("1", "f97"), ("f98", "f59"), ("1", "f92"), ("f100", "1"), ("1", "f101"), ("f99", "1"), ("f102", "f103"), ("f104", "1")],
        },
        ParametricChain {
            variables: &["a", "b", "c", "d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a"), ("f4", "1"), ("1", "f5"), ("1", "d"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "d"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b"), ("f23", "1"), ("1", "f24"), ("1", "c"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "c"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42"), ("1", "1"), ("f44", "1"), ("1", "f45"), ("1", "f46"), ("f47", "1"), ("1", "f48"), ("f49", "f43"), ("f50", "1"), ("1", "1"), ("f52", "1"), ("1", "f53"), ("1", "f54"), ("f55", "1"), ("1", "f56"), ("b", "1"), ("f57", "f58"), ("1", "1"), ("f60", "1"), ("1", "f61"), ("1", "f62"), ("f63", "1"), ("1", "f64"), ("c", "1"), ("f65", "f66"), ("1", "1"), ("f68", "1"), ("1", "f69"), ("1", "f51"), ("f71", "1"), ("1", "f72"), ("1", "d"), ("f74", "1"), ("1", "f75"), ("1", "f70"), ("f77", "1"), ("1", "f78"), ("f79", "d"), ("1", "f73"), ("f81", "1"), ("1", "f82"), ("f80", "1"), ("f83", "f84"), ("f85", "1"), ("1", "1"), ("f87", "1"), ("1", "f88"), ("1", "f51"), ("f90", "1"), ("1", "f91"), ("1", "f59"), ("f93", "1"), ("1", "f94"), ("1", "f89"), ("f96", "1"), ("1", "f97"), ("f98", "f59"), ("1", "f92"), ("f100", "1"), ("1", "f101"), ("f99", "1"), ("f102", "f103"), ("f104", "1"), ("1", "1"), ("f106", "1"), ("1", "f107"), ("1", "f51"), ("f109", "1"), ("1", "f110"), ("1", "f67"), ("f112", "1"), ("1", "f113"), ("1", "f108"), ("f115", "1"), ("1", "f116"), ("f117", "f67"), ("1", "f111"), ("f119", "1"), ("1", "f120"), ("f118", "1"), ("f121", "f122"), ("f123", "1")],
        },
        ParametricChain {
            variables: &["a", "b", "c", "d"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a"), ("f4", "1"), ("1", "f5"), ("1", "d"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "d"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b"), ("f23", "1"), ("1", "f24"), ("1", "c"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "c"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42"), ("1", "1"), ("f44", "1"), ("1", "f45"), ("1", "f46"), ("f47", "1"), ("1", "f48"), ("f49", "f43"), ("f50", "1"), ("1", "1"), ("f52", "1"), ("1", "f53"), ("1", "f54"), ("f55", "1"), ("1", "f56"), ("b", "1"), ("f57", "f58"), ("1", "1"), ("f60", "1"), ("1", "f61"), ("1", "f62"), ("f63", "1"), ("1", "f64"), ("c", "1"), ("f65", "f66"), ("1", "1"), ("f68", "1"), ("1", "f69"), ("1", "f51"), ("f71", "1"), ("1", "f72"), ("1", "d"), ("f74", "1"), ("1", "f75"), ("1", "f70"), ("f77", "1"), ("1", "f78"), ("f79", "d"), ("1", "f73"), ("f81", "1"), ("1", "f82"), ("f80", "1"), ("f83", "f84"), ("f85", "1"), ("1", "1"), ("f87", "1"), ("1", "f88"), ("1", "f51"), ("f90", "1"), ("1", "f91"), ("1", "f59"), ("f93", "1"), ("1", "f94"), ("1", "f89"), ("f96", "1"), ("1", "f97"), ("f98", "f59"), ("1", "f92"), ("f100", "1"), ("1", "f101"), ("f99", "1"), ("f102", "f103"), ("f104", "1"), ("1", "1"), ("f106", "1"), ("1", "f107"), ("1", "f51"), ("f109", "1"), ("1", "f110"), ("1", "f67"), ("f112", "1"), ("1", "f113"), ("1", "f108"), ("f115", "1"), ("1", "f116"), ("f117", "f67"), ("1", "f111"), ("f119", "1"), ("1", "f120"), ("f118", "1"), ("f121", "f122"), ("f123", "1"), ("1", "1"), ("f125", "1"), ("1", "f126"), ("1", "f51"), ("f128", "1"), ("1", "f129"), ("1", "a"), ("f131", "1"), ("1", "f132"), ("1", "f127"), ("f134", "1"), ("1", "f135"), ("f136", "a"), ("1", "f130"), ("f138", "1"), ("1", "f139"), ("f137", "1"), ("f140", "f141"), ("f142", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "2x2 matrix inverse",
    },
    MacroDefinition {
        shorthand_id: "LIN",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a", "x", "b"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("b", "1"), ("f12", "f20"), ("1", "f19"), ("f22", "1"), ("1", "f23"), ("f21", "1"), ("f24", "f25")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "y = a*x + b (linear calibration)",
    },
    MacroDefinition {
        shorthand_id: "LL2",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "x"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "ln(ln(x))",
    },
    MacroDefinition {
        shorthand_id: "LL3",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "x"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("1", "f6"), ("f7", "1"), ("1", "f8")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "ln^3(x) = ln(ln(ln(x)))",
    },
    MacroDefinition {
        shorthand_id: "LOG",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "x"), ("f1", "1"), ("1", "f2")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "ln(x) = eml(1, eml(eml(1,x), 1))",
    },
    MacroDefinition {
        shorthand_id: "LRL",
        function_class: FunctionClass::NnActivation,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "alpha", "half"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "alpha"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "x"), ("f20", "1"), ("1", "f21"), ("f19", "1"), ("f22", "f23"), ("1", "1"), ("f25", "1"), ("1", "f26"), ("1", "f27"), ("f28", "1"), ("1", "f29"), ("x", "1"), ("f30", "f31"), ("1", "f19"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("1", "1"), ("f38", "1"), ("1", "f39"), ("1", "f24"), ("f41", "1"), ("1", "f42"), ("1", "f24"), ("f44", "1"), ("1", "f45"), ("1", "f40"), ("f47", "1"), ("1", "f48"), ("f49", "f24"), ("1", "f43"), ("f51", "1"), ("1", "f52"), ("f50", "1"), ("f53", "f54"), ("f55", "1"), ("1", "f56"), ("f57", "1"), ("1", "f58"), ("1", "1"), ("f60", "1"), ("1", "f61"), ("1", "half"), ("f63", "1"), ("1", "f64"), ("1", "f59"), ("f66", "1"), ("1", "f67"), ("1", "f62"), ("f69", "1"), ("1", "f70"), ("f71", "f59"), ("1", "f65"), ("f73", "1"), ("1", "f74"), ("f72", "1"), ("f75", "f76"), ("f77", "1"), ("f78", "1"), ("1", "1"), ("f80", "1"), ("1", "f81"), ("1", "f82"), ("f83", "1"), ("1", "f84"), ("f79", "1"), ("f85", "f86"), ("1", "f37"), ("f88", "1"), ("1", "f89"), ("f87", "1"), ("f90", "f91"), ("1", "1"), ("f93", "1"), ("1", "f94"), ("1", "f92"), ("f96", "1"), ("1", "f97"), ("1", "half"), ("f99", "1"), ("1", "f100"), ("1", "f95"), ("f102", "1"), ("1", "f103"), ("f104", "half"), ("1", "f98"), ("f106", "1"), ("1", "f107"), ("f105", "1"), ("f108", "f109"), ("f110", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Leaky ReLU",
    },
    MacroDefinition {
        shorthand_id: "LRP",
        function_class: FunctionClass::NumericalMethod,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a", "b", "t"],
            levels: &[("1", "b"), ("f1", "1"), ("1", "f2"), ("a", "1"), ("f3", "f4"), ("1", "1"), ("f6", "1"), ("1", "f7"), ("1", "t"), ("f9", "1"), ("1", "f10"), ("1", "f5"), ("f12", "1"), ("1", "f13"), ("1", "f8"), ("f15", "1"), ("1", "f16"), ("f17", "f5"), ("1", "f11"), ("f19", "1"), ("1", "f20"), ("f18", "1"), ("f21", "f22"), ("f23", "1"), ("1", "1"), ("f25", "1"), ("1", "f26"), ("1", "f27"), ("f28", "1"), ("1", "f29"), ("f24", "1"), ("f30", "f31"), ("1", "a"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "linear interpolation a + t*(b-a)",
    },
    MacroDefinition {
        shorthand_id: "LRZ",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["beta", "one", "half"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "beta"), ("f4", "1"), ("1", "f5"), ("1", "beta"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "beta"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "one"), ("f20", "1"), ("1", "f21"), ("f19", "1"), ("f22", "f23"), ("1", "f24"), ("f25", "1"), ("1", "f26"), ("1", "1"), ("f28", "1"), ("1", "f29"), ("1", "half"), ("f31", "1"), ("1", "f32"), ("1", "f27"), ("f34", "1"), ("1", "f35"), ("1", "f30"), ("f37", "1"), ("1", "f38"), ("f39", "f27"), ("1", "f33"), ("f41", "1"), ("1", "f42"), ("f40", "1"), ("f43", "f44"), ("f45", "1"), ("f46", "1"), ("1", "one"), ("f48", "1"), ("1", "f49"), ("1", "f50"), ("f51", "1"), ("1", "f52"), ("f53", "f47"), ("f54", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Lorentz gamma 1/sqrt(1 - beta^2)",
    },
    MacroDefinition {
        shorthand_id: "LST",
        function_class: FunctionClass::NnLayer,
        variant_tag: VariantTag::MultiOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "h_prev", "c_prev", "W_i", "U_i", "b_i", "W_f", "U_f", "b_f", "W_g", "U_g", "b_g", "W_o", "U_o", "b_o"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "W_i"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "U_i"), ("f23", "1"), ("1", "f24"), ("1", "h_prev"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "h_prev"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f41"), ("f42", "1"), ("1", "f43"), ("f38", "1"), ("f44", "f45"), ("1", "f19"), ("f47", "1"), ("1", "f48"), ("f46", "1"), ("f49", "f50"), ("1", "1"), ("f52", "1"), ("1", "f53"), ("1", "f54"), ("f55", "1"), ("1", "f56"), ("b_i", "1"), ("f57", "f58"), ("1", "f51"), ("f60", "1"), ("1", "f61"), ("f59", "1"), ("f62", "f63"), ("1", "1"), ("f65", "1"), ("1", "f66"), ("1", "f67"), ("f68", "1"), ("1", "f69"), ("f64", "1"), ("f70", "f71"), ("f72", "1"), ("1", "1"), ("f74", "1"), ("1", "f75"), ("1", "f76"), ("f77", "1"), ("1", "f78"), ("f73", "1"), ("f79", "f80"), ("1", "1"), ("f82", "1"), ("1", "f83"), ("f81", "1"), ("f84", "f85"), ("1", "1"), ("f87", "1"), ("1", "f88"), ("1", "f89"), ("f90", "1"), ("1", "f91"), ("f92", "f86"), ("f93", "1"), ("1", "1"), ("f95", "1"), ("1", "f96"), ("1", "W_f"), ("f98", "1"), ("1", "f99"), ("1", "x"), ("f101", "1"), ("1", "f102"), ("1", "f97"), ("f104", "1"), ("1", "f105"), ("f106", "x"), ("1", "f100"), ("f108", "1"), ("1", "f109"), ("f107", "1"), ("f110", "f111"), ("f112", "1"), ("1", "1"), ("f114", "1"), ("1", "f115"), ("1", "U_f"), ("f117", "1"), ("1", "f118"), ("1", "h_prev"), ("f120", "1"), ("1", "f121"), ("1", "f116"), ("f123", "1"), ("1", "f124"), ("f125", "h_prev"), ("1", "f119"), ("f127", "1"), ("1", "f128"), ("f126", "1"), ("f129", "f130"), ("f131", "1"), ("1", "1"), ("f133", "1"), ("1", "f134"), ("1", "f135"), ("f136", "1"), ("1", "f137"), ("f132", "1"), ("f138", "f139"), ("1", "f113"), ("f141", "1"), ("1", "f142"), ("f140", "1"), ("f143", "f144"), ("1", "1"), ("f146", "1"), ("1", "f147"), ("1", "f148"), ("f149", "1"), ("1", "f150"), ("b_f", "1"), ("f151", "f152"), ("1", "f145"), ("f154", "1"), ("1", "f155"), ("f153", "1"), ("f156", "f157"), ("1", "1"), ("f159", "1"), ("1", "f160"), ("1", "f161"), ("f162", "1"), ("1", "f163"), ("f158", "1"), ("f164", "f165"), ("f166", "1"), ("1", "1"), ("f168", "1"), ("1", "f169"), ("1", "f170"), ("f171", "1"), ("1", "f172"), ("f167", "1"), ("f173", "f174"), ("1", "1"), ("f176", "1"), ("1", "f177"), ("f175", "1"), ("f178", "f179"), ("1", "1"), ("f181", "1"), ("1", "f182"), ("1", "f183"), ("f184", "1"), ("1", "f185"), ("f186", "f180"), ("f187", "1"), ("1", "1"), ("f189", "1"), ("1", "f190"), ("1", "W_g"), ("f192", "1"), ("1", "f193"), ("1", "x"), ("f195", "1"), ("1", "f196"), ("1", "f191"), ("f198", "1"), ("1", "f199"), ("f200", "x"), ("1", "f194"), ("f202", "1"), ("1", "f203"), ("f201", "1"), ("f204", "f205"), ("f206", "1"), ("1", "1"), ("f208", "1"), ("1", "f209"), ("1", "U_g"), ("f211", "1"), ("1", "f212"), ("1", "h_prev"), ("f214", "1"), ("1", "f215"), ("1", "f210"), ("f217", "1"), ("1", "f218"), ("f219", "h_prev"), ("1", "f213"), ("f221", "1"), ("1", "f222"), ("f220", "1"), ("f223", "f224"), ("f225", "1"), ("1", "1"), ("f227", "1"), ("1", "f228"), ("1", "f229"), ("f230", "1"), ("1", "f231"), ("f226", "1"), ("f232", "f233"), ("1", "f207"), ("f235", "1"), ("1", "f236"), ("f234", "1"), ("f237", "f238"), ("1", "1"), ("f240", "1"), ("1", "f241"), ("1", "f242"), ("f243", "1"), ("1", "f244"), ("b_g", "1"), ("f245", "f246"), ("1", "f239"), ("f248", "1"), ("1", "f249"), ("f247", "1"), ("f250", "f251"), ("f252", "1"), ("1", "1"), ("f254", "1"), ("1", "f255"), ("1", "f256"), ("f257", "1"), ("1", "f258"), ("f252", "1"), ("f259", "f260"), ("f261", "1"), ("1", "f253"), ("f263", "1"), ("1", "f264"), ("f262", "1"), ("f265", "f266"), ("1", "1"), ("f268", "1"), ("1", "f269"), ("1", "f270"), ("f271", "1"), ("1", "f272"), ("f262", "1"), ("f273", "f274"), ("1", "f253"), ("f276", "1"), ("1", "f277"), ("f275", "1"), ("f278", "f279"), ("1", "f267"), ("f281", "1"), ("1", "f282"), ("1", "f283"), ("f284", "1"), ("1", "f285"), ("f286", "f280"), ("f287", "1"), ("1", "1"), ("f289", "1"), ("1", "f290"), ("1", "W_o"), ("f292", "1"), ("1", "f293"), ("1", "x"), ("f295", "1"), ("1", "f296"), ("1", "f291"), ("f298", "1"), ("1", "f299"), ("f300", "x"), ("1", "f294"), ("f302", "1"), ("1", "f303"), ("f301", "1"), ("f304", "f305"), ("f306", "1"), ("1", "1"), ("f308", "1"), ("1", "f309"), ("1", "U_o"), ("f311", "1"), ("1", "f312"), ("1", "h_prev"), ("f314", "1"), ("1", "f315"), ("1", "f310"), ("f317", "1"), ("1", "f318"), ("f319", "h_prev"), ("1", "f313"), ("f321", "1"), ("1", "f322"), ("f320", "1"), ("f323", "f324"), ("f325", "1"), ("1", "1"), ("f327", "1"), ("1", "f328"), ("1", "f329"), ("f330", "1"), ("1", "f331"), ("f326", "1"), ("f332", "f333"), ("1", "f307"), ("f335", "1"), ("1", "f336"), ("f334", "1"), ("f337", "f338"), ("1", "1"), ("f340", "1"), ("1", "f341"), ("1", "f342"), ("f343", "1"), ("1", "f344"), ("b_o", "1"), ("f345", "f346"), ("1", "f339"), ("f348", "1"), ("1", "f349"), ("f347", "1"), ("f350", "f351"), ("1", "1"), ("f353", "1"), ("1", "f354"), ("1", "f355"), ("f356", "1"), ("1", "f357"), ("f352", "1"), ("f358", "f359"), ("f360", "1"), ("1", "1"), ("f362", "1"), ("1", "f363"), ("1", "f364"), ("f365", "1"), ("1", "f366"), ("f361", "1"), ("f367", "f368"), ("1", "1"), ("f370", "1"), ("1", "f371"), ("f369", "1"), ("f372", "f373"), ("1", "1"), ("f375", "1"), ("1", "f376"), ("1", "f377"), ("f378", "1"), ("1", "f379"), ("f380", "f374"), ("f381", "1"), ("1", "1"), ("f383", "1"), ("1", "f384"), ("1", "f188"), ("f386", "1"), ("1", "f387"), ("1", "c_prev"), ("f389", "1"), ("1", "f390"), ("1", "f385"), ("f392", "1"), ("1", "f393"), ("f394", "c_prev"), ("1", "f388"), ("f396", "1"), ("1", "f397"), ("f395", "1"), ("f398", "f399"), ("f400", "1"), ("1", "1"), ("f402", "1"), ("1", "f403"), ("1", "f94"), ("f405", "1"), ("1", "f406"), ("1", "f288"), ("f408", "1"), ("1", "f409"), ("1", "f404"), ("f411", "1"), ("1", "f412"), ("f413", "f288"), ("1", "f407"), ("f415", "1"), ("1", "f416"), ("f414", "1"), ("f417", "f418"), ("f419", "1"), ("1", "1"), ("f421", "1"), ("1", "f422"), ("1", "f423"), ("f424", "1"), ("1", "f425"), ("f420", "1"), ("f426", "f427"), ("1", "f401"), ("f429", "1"), ("1", "f430"), ("f428", "1"), ("f431", "f432"), ("f433", "1"), ("1", "1"), ("f435", "1"), ("1", "f436"), ("1", "f437"), ("f438", "1"), ("1", "f439"), ("f433", "1"), ("f440", "f441"), ("f442", "1"), ("1", "f434"), ("f444", "1"), ("1", "f445"), ("f443", "1"), ("f446", "f447"), ("1", "1"), ("f449", "1"), ("1", "f450"), ("1", "f451"), ("f452", "1"), ("1", "f453"), ("f443", "1"), ("f454", "f455"), ("1", "f434"), ("f457", "1"), ("1", "f458"), ("f456", "1"), ("f459", "f460"), ("1", "f448"), ("f462", "1"), ("1", "f463"), ("1", "f464"), ("f465", "1"), ("1", "f466"), ("f467", "f461"), ("f468", "1"), ("1", "1"), ("f470", "1"), ("1", "f471"), ("1", "f382"), ("f473", "1"), ("1", "f474"), ("1", "f469"), ("f476", "1"), ("1", "f477"), ("1", "f472"), ("f479", "1"), ("1", "f480"), ("f481", "f469"), ("1", "f475"), ("f483", "1"), ("1", "f484"), ("f482", "1"), ("f485", "f486"), ("f487", "1")],
        },
        ParametricChain {
            variables: &["x", "h_prev", "c_prev", "W_i", "U_i", "b_i", "W_f", "U_f", "b_f", "W_g", "U_g", "b_g", "W_o", "U_o", "b_o"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "W_i"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "U_i"), ("f23", "1"), ("1", "f24"), ("1", "h_prev"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "h_prev"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f41"), ("f42", "1"), ("1", "f43"), ("f38", "1"), ("f44", "f45"), ("1", "f19"), ("f47", "1"), ("1", "f48"), ("f46", "1"), ("f49", "f50"), ("1", "1"), ("f52", "1"), ("1", "f53"), ("1", "f54"), ("f55", "1"), ("1", "f56"), ("b_i", "1"), ("f57", "f58"), ("1", "f51"), ("f60", "1"), ("1", "f61"), ("f59", "1"), ("f62", "f63"), ("1", "1"), ("f65", "1"), ("1", "f66"), ("1", "f67"), ("f68", "1"), ("1", "f69"), ("f64", "1"), ("f70", "f71"), ("f72", "1"), ("1", "1"), ("f74", "1"), ("1", "f75"), ("1", "f76"), ("f77", "1"), ("1", "f78"), ("f73", "1"), ("f79", "f80"), ("1", "1"), ("f82", "1"), ("1", "f83"), ("f81", "1"), ("f84", "f85"), ("1", "1"), ("f87", "1"), ("1", "f88"), ("1", "f89"), ("f90", "1"), ("1", "f91"), ("f92", "f86"), ("f93", "1"), ("1", "1"), ("f95", "1"), ("1", "f96"), ("1", "W_f"), ("f98", "1"), ("1", "f99"), ("1", "x"), ("f101", "1"), ("1", "f102"), ("1", "f97"), ("f104", "1"), ("1", "f105"), ("f106", "x"), ("1", "f100"), ("f108", "1"), ("1", "f109"), ("f107", "1"), ("f110", "f111"), ("f112", "1"), ("1", "1"), ("f114", "1"), ("1", "f115"), ("1", "U_f"), ("f117", "1"), ("1", "f118"), ("1", "h_prev"), ("f120", "1"), ("1", "f121"), ("1", "f116"), ("f123", "1"), ("1", "f124"), ("f125", "h_prev"), ("1", "f119"), ("f127", "1"), ("1", "f128"), ("f126", "1"), ("f129", "f130"), ("f131", "1"), ("1", "1"), ("f133", "1"), ("1", "f134"), ("1", "f135"), ("f136", "1"), ("1", "f137"), ("f132", "1"), ("f138", "f139"), ("1", "f113"), ("f141", "1"), ("1", "f142"), ("f140", "1"), ("f143", "f144"), ("1", "1"), ("f146", "1"), ("1", "f147"), ("1", "f148"), ("f149", "1"), ("1", "f150"), ("b_f", "1"), ("f151", "f152"), ("1", "f145"), ("f154", "1"), ("1", "f155"), ("f153", "1"), ("f156", "f157"), ("1", "1"), ("f159", "1"), ("1", "f160"), ("1", "f161"), ("f162", "1"), ("1", "f163"), ("f158", "1"), ("f164", "f165"), ("f166", "1"), ("1", "1"), ("f168", "1"), ("1", "f169"), ("1", "f170"), ("f171", "1"), ("1", "f172"), ("f167", "1"), ("f173", "f174"), ("1", "1"), ("f176", "1"), ("1", "f177"), ("f175", "1"), ("f178", "f179"), ("1", "1"), ("f181", "1"), ("1", "f182"), ("1", "f183"), ("f184", "1"), ("1", "f185"), ("f186", "f180"), ("f187", "1"), ("1", "1"), ("f189", "1"), ("1", "f190"), ("1", "W_g"), ("f192", "1"), ("1", "f193"), ("1", "x"), ("f195", "1"), ("1", "f196"), ("1", "f191"), ("f198", "1"), ("1", "f199"), ("f200", "x"), ("1", "f194"), ("f202", "1"), ("1", "f203"), ("f201", "1"), ("f204", "f205"), ("f206", "1"), ("1", "1"), ("f208", "1"), ("1", "f209"), ("1", "U_g"), ("f211", "1"), ("1", "f212"), ("1", "h_prev"), ("f214", "1"), ("1", "f215"), ("1", "f210"), ("f217", "1"), ("1", "f218"), ("f219", "h_prev"), ("1", "f213"), ("f221", "1"), ("1", "f222"), ("f220", "1"), ("f223", "f224"), ("f225", "1"), ("1", "1"), ("f227", "1"), ("1", "f228"), ("1", "f229"), ("f230", "1"), ("1", "f231"), ("f226", "1"), ("f232", "f233"), ("1", "f207"), ("f235", "1"), ("1", "f236"), ("f234", "1"), ("f237", "f238"), ("1", "1"), ("f240", "1"), ("1", "f241"), ("1", "f242"), ("f243", "1"), ("1", "f244"), ("b_g", "1"), ("f245", "f246"), ("1", "f239"), ("f248", "1"), ("1", "f249"), ("f247", "1"), ("f250", "f251"), ("f252", "1"), ("1", "1"), ("f254", "1"), ("1", "f255"), ("1", "f256"), ("f257", "1"), ("1", "f258"), ("f252", "1"), ("f259", "f260"), ("f261", "1"), ("1", "f253"), ("f263", "1"), ("1", "f264"), ("f262", "1"), ("f265", "f266"), ("1", "1"), ("f268", "1"), ("1", "f269"), ("1", "f270"), ("f271", "1"), ("1", "f272"), ("f262", "1"), ("f273", "f274"), ("1", "f253"), ("f276", "1"), ("1", "f277"), ("f275", "1"), ("f278", "f279"), ("1", "f267"), ("f281", "1"), ("1", "f282"), ("1", "f283"), ("f284", "1"), ("1", "f285"), ("f286", "f280"), ("f287", "1"), ("1", "1"), ("f289", "1"), ("1", "f290"), ("1", "W_o"), ("f292", "1"), ("1", "f293"), ("1", "x"), ("f295", "1"), ("1", "f296"), ("1", "f291"), ("f298", "1"), ("1", "f299"), ("f300", "x"), ("1", "f294"), ("f302", "1"), ("1", "f303"), ("f301", "1"), ("f304", "f305"), ("f306", "1"), ("1", "1"), ("f308", "1"), ("1", "f309"), ("1", "U_o"), ("f311", "1"), ("1", "f312"), ("1", "h_prev"), ("f314", "1"), ("1", "f315"), ("1", "f310"), ("f317", "1"), ("1", "f318"), ("f319", "h_prev"), ("1", "f313"), ("f321", "1"), ("1", "f322"), ("f320", "1"), ("f323", "f324"), ("f325", "1"), ("1", "1"), ("f327", "1"), ("1", "f328"), ("1", "f329"), ("f330", "1"), ("1", "f331"), ("f326", "1"), ("f332", "f333"), ("1", "f307"), ("f335", "1"), ("1", "f336"), ("f334", "1"), ("f337", "f338"), ("1", "1"), ("f340", "1"), ("1", "f341"), ("1", "f342"), ("f343", "1"), ("1", "f344"), ("b_o", "1"), ("f345", "f346"), ("1", "f339"), ("f348", "1"), ("1", "f349"), ("f347", "1"), ("f350", "f351"), ("1", "1"), ("f353", "1"), ("1", "f354"), ("1", "f355"), ("f356", "1"), ("1", "f357"), ("f352", "1"), ("f358", "f359"), ("f360", "1"), ("1", "1"), ("f362", "1"), ("1", "f363"), ("1", "f364"), ("f365", "1"), ("1", "f366"), ("f361", "1"), ("f367", "f368"), ("1", "1"), ("f370", "1"), ("1", "f371"), ("f369", "1"), ("f372", "f373"), ("1", "1"), ("f375", "1"), ("1", "f376"), ("1", "f377"), ("f378", "1"), ("1", "f379"), ("f380", "f374"), ("f381", "1"), ("1", "1"), ("f383", "1"), ("1", "f384"), ("1", "f188"), ("f386", "1"), ("1", "f387"), ("1", "c_prev"), ("f389", "1"), ("1", "f390"), ("1", "f385"), ("f392", "1"), ("1", "f393"), ("f394", "c_prev"), ("1", "f388"), ("f396", "1"), ("1", "f397"), ("f395", "1"), ("f398", "f399"), ("f400", "1"), ("1", "1"), ("f402", "1"), ("1", "f403"), ("1", "f94"), ("f405", "1"), ("1", "f406"), ("1", "f288"), ("f408", "1"), ("1", "f409"), ("1", "f404"), ("f411", "1"), ("1", "f412"), ("f413", "f288"), ("1", "f407"), ("f415", "1"), ("1", "f416"), ("f414", "1"), ("f417", "f418"), ("f419", "1"), ("1", "1"), ("f421", "1"), ("1", "f422"), ("1", "f423"), ("f424", "1"), ("1", "f425"), ("f420", "1"), ("f426", "f427"), ("1", "f401"), ("f429", "1"), ("1", "f430"), ("f428", "1"), ("f431", "f432")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "LSTM cell scalar update (h_new, c_new)",
    },
    MacroDefinition {
        shorthand_id: "LSX",
        function_class: FunctionClass::NnActivation,
        variant_tag: VariantTag::MultiOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x1", "x2", "x3"],
            levels: &[("x1", "1"), ("x2", "1"), ("x3", "1"), ("1", "1"), ("f4", "1"), ("1", "f5"), ("1", "f6"), ("f7", "1"), ("1", "f8"), ("f2", "1"), ("f9", "f10"), ("1", "f1"), ("f12", "1"), ("1", "f13"), ("f11", "1"), ("f14", "f15"), ("1", "1"), ("f17", "1"), ("1", "f18"), ("1", "f19"), ("f20", "1"), ("1", "f21"), ("f3", "1"), ("f22", "f23"), ("1", "f16"), ("f25", "1"), ("1", "f26"), ("f24", "1"), ("f27", "f28"), ("1", "f29"), ("f30", "1"), ("1", "f31"), ("1", "x1"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36")],
        },
        ParametricChain {
            variables: &["x1", "x2", "x3"],
            levels: &[("x1", "1"), ("x2", "1"), ("x3", "1"), ("1", "1"), ("f4", "1"), ("1", "f5"), ("1", "f6"), ("f7", "1"), ("1", "f8"), ("f2", "1"), ("f9", "f10"), ("1", "f1"), ("f12", "1"), ("1", "f13"), ("f11", "1"), ("f14", "f15"), ("1", "1"), ("f17", "1"), ("1", "f18"), ("1", "f19"), ("f20", "1"), ("1", "f21"), ("f3", "1"), ("f22", "f23"), ("1", "f16"), ("f25", "1"), ("1", "f26"), ("f24", "1"), ("f27", "f28"), ("1", "f29"), ("f30", "1"), ("1", "f31"), ("1", "x1"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("1", "x2"), ("f38", "1"), ("1", "f39"), ("f32", "1"), ("f40", "f41")],
        },
        ParametricChain {
            variables: &["x1", "x2", "x3"],
            levels: &[("x1", "1"), ("x2", "1"), ("x3", "1"), ("1", "1"), ("f4", "1"), ("1", "f5"), ("1", "f6"), ("f7", "1"), ("1", "f8"), ("f2", "1"), ("f9", "f10"), ("1", "f1"), ("f12", "1"), ("1", "f13"), ("f11", "1"), ("f14", "f15"), ("1", "1"), ("f17", "1"), ("1", "f18"), ("1", "f19"), ("f20", "1"), ("1", "f21"), ("f3", "1"), ("f22", "f23"), ("1", "f16"), ("f25", "1"), ("1", "f26"), ("f24", "1"), ("f27", "f28"), ("1", "f29"), ("f30", "1"), ("1", "f31"), ("1", "x1"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("1", "x2"), ("f38", "1"), ("1", "f39"), ("f32", "1"), ("f40", "f41"), ("1", "x3"), ("f43", "1"), ("1", "f44"), ("f32", "1"), ("f45", "f46")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "log-softmax3 (3-class)",
    },
    MacroDefinition {
        shorthand_id: "MMG",
        function_class: FunctionClass::LinAlg,
        variant_tag: VariantTag::MultiOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a11", "a12", "a13", "a21", "a22", "a23", "a31", "a32", "a33", "b11", "b12", "b13", "b21", "b22", "b23", "b31", "b32", "b33"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a11"), ("f4", "1"), ("1", "f5"), ("1", "b11"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "b11"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "a12"), ("f23", "1"), ("1", "f24"), ("1", "b21"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b21"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "a13"), ("f42", "1"), ("1", "f43"), ("1", "b31"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "b31"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f60"), ("f61", "1"), ("1", "f62"), ("f38", "1"), ("f63", "f64"), ("1", "f19"), ("f66", "1"), ("1", "f67"), ("f65", "1"), ("f68", "f69"), ("1", "1"), ("f71", "1"), ("1", "f72"), ("1", "f73"), ("f74", "1"), ("1", "f75"), ("f57", "1"), ("f76", "f77"), ("1", "f70"), ("f79", "1"), ("1", "f80"), ("f78", "1"), ("f81", "f82")],
        },
        ParametricChain {
            variables: &["a11", "a12", "a13", "a21", "a22", "a23", "a31", "a32", "a33", "b11", "b12", "b13", "b21", "b22", "b23", "b31", "b32", "b33"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a11"), ("f4", "1"), ("1", "f5"), ("1", "b11"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "b11"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "a12"), ("f23", "1"), ("1", "f24"), ("1", "b21"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b21"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "a13"), ("f42", "1"), ("1", "f43"), ("1", "b31"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "b31"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f60"), ("f61", "1"), ("1", "f62"), ("f38", "1"), ("f63", "f64"), ("1", "f19"), ("f66", "1"), ("1", "f67"), ("f65", "1"), ("f68", "f69"), ("1", "1"), ("f71", "1"), ("1", "f72"), ("1", "f73"), ("f74", "1"), ("1", "f75"), ("f57", "1"), ("f76", "f77"), ("1", "f70"), ("f79", "1"), ("1", "f80"), ("f78", "1"), ("f81", "f82"), ("1", "1"), ("f84", "1"), ("1", "f85"), ("1", "a11"), ("f87", "1"), ("1", "f88"), ("1", "b12"), ("f90", "1"), ("1", "f91"), ("1", "f86"), ("f93", "1"), ("1", "f94"), ("f95", "b12"), ("1", "f89"), ("f97", "1"), ("1", "f98"), ("f96", "1"), ("f99", "f100"), ("f101", "1"), ("1", "1"), ("f103", "1"), ("1", "f104"), ("1", "a12"), ("f106", "1"), ("1", "f107"), ("1", "b22"), ("f109", "1"), ("1", "f110"), ("1", "f105"), ("f112", "1"), ("1", "f113"), ("f114", "b22"), ("1", "f108"), ("f116", "1"), ("1", "f117"), ("f115", "1"), ("f118", "f119"), ("f120", "1"), ("1", "1"), ("f122", "1"), ("1", "f123"), ("1", "a13"), ("f125", "1"), ("1", "f126"), ("1", "b32"), ("f128", "1"), ("1", "f129"), ("1", "f124"), ("f131", "1"), ("1", "f132"), ("f133", "b32"), ("1", "f127"), ("f135", "1"), ("1", "f136"), ("f134", "1"), ("f137", "f138"), ("f139", "1"), ("1", "1"), ("f141", "1"), ("1", "f142"), ("1", "f143"), ("f144", "1"), ("1", "f145"), ("f121", "1"), ("f146", "f147"), ("1", "f102"), ("f149", "1"), ("1", "f150"), ("f148", "1"), ("f151", "f152"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "f156"), ("f157", "1"), ("1", "f158"), ("f140", "1"), ("f159", "f160"), ("1", "f153"), ("f162", "1"), ("1", "f163"), ("f161", "1"), ("f164", "f165")],
        },
        ParametricChain {
            variables: &["a11", "a12", "a13", "a21", "a22", "a23", "a31", "a32", "a33", "b11", "b12", "b13", "b21", "b22", "b23", "b31", "b32", "b33"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a11"), ("f4", "1"), ("1", "f5"), ("1", "b11"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "b11"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "a12"), ("f23", "1"), ("1", "f24"), ("1", "b21"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b21"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "a13"), ("f42", "1"), ("1", "f43"), ("1", "b31"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "b31"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f60"), ("f61", "1"), ("1", "f62"), ("f38", "1"), ("f63", "f64"), ("1", "f19"), ("f66", "1"), ("1", "f67"), ("f65", "1"), ("f68", "f69"), ("1", "1"), ("f71", "1"), ("1", "f72"), ("1", "f73"), ("f74", "1"), ("1", "f75"), ("f57", "1"), ("f76", "f77"), ("1", "f70"), ("f79", "1"), ("1", "f80"), ("f78", "1"), ("f81", "f82"), ("1", "1"), ("f84", "1"), ("1", "f85"), ("1", "a11"), ("f87", "1"), ("1", "f88"), ("1", "b12"), ("f90", "1"), ("1", "f91"), ("1", "f86"), ("f93", "1"), ("1", "f94"), ("f95", "b12"), ("1", "f89"), ("f97", "1"), ("1", "f98"), ("f96", "1"), ("f99", "f100"), ("f101", "1"), ("1", "1"), ("f103", "1"), ("1", "f104"), ("1", "a12"), ("f106", "1"), ("1", "f107"), ("1", "b22"), ("f109", "1"), ("1", "f110"), ("1", "f105"), ("f112", "1"), ("1", "f113"), ("f114", "b22"), ("1", "f108"), ("f116", "1"), ("1", "f117"), ("f115", "1"), ("f118", "f119"), ("f120", "1"), ("1", "1"), ("f122", "1"), ("1", "f123"), ("1", "a13"), ("f125", "1"), ("1", "f126"), ("1", "b32"), ("f128", "1"), ("1", "f129"), ("1", "f124"), ("f131", "1"), ("1", "f132"), ("f133", "b32"), ("1", "f127"), ("f135", "1"), ("1", "f136"), ("f134", "1"), ("f137", "f138"), ("f139", "1"), ("1", "1"), ("f141", "1"), ("1", "f142"), ("1", "f143"), ("f144", "1"), ("1", "f145"), ("f121", "1"), ("f146", "f147"), ("1", "f102"), ("f149", "1"), ("1", "f150"), ("f148", "1"), ("f151", "f152"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "f156"), ("f157", "1"), ("1", "f158"), ("f140", "1"), ("f159", "f160"), ("1", "f153"), ("f162", "1"), ("1", "f163"), ("f161", "1"), ("f164", "f165"), ("1", "1"), ("f167", "1"), ("1", "f168"), ("1", "a11"), ("f170", "1"), ("1", "f171"), ("1", "b13"), ("f173", "1"), ("1", "f174"), ("1", "f169"), ("f176", "1"), ("1", "f177"), ("f178", "b13"), ("1", "f172"), ("f180", "1"), ("1", "f181"), ("f179", "1"), ("f182", "f183"), ("f184", "1"), ("1", "1"), ("f186", "1"), ("1", "f187"), ("1", "a12"), ("f189", "1"), ("1", "f190"), ("1", "b23"), ("f192", "1"), ("1", "f193"), ("1", "f188"), ("f195", "1"), ("1", "f196"), ("f197", "b23"), ("1", "f191"), ("f199", "1"), ("1", "f200"), ("f198", "1"), ("f201", "f202"), ("f203", "1"), ("1", "1"), ("f205", "1"), ("1", "f206"), ("1", "a13"), ("f208", "1"), ("1", "f209"), ("1", "b33"), ("f211", "1"), ("1", "f212"), ("1", "f207"), ("f214", "1"), ("1", "f215"), ("f216", "b33"), ("1", "f210"), ("f218", "1"), ("1", "f219"), ("f217", "1"), ("f220", "f221"), ("f222", "1"), ("1", "1"), ("f224", "1"), ("1", "f225"), ("1", "f226"), ("f227", "1"), ("1", "f228"), ("f204", "1"), ("f229", "f230"), ("1", "f185"), ("f232", "1"), ("1", "f233"), ("f231", "1"), ("f234", "f235"), ("1", "1"), ("f237", "1"), ("1", "f238"), ("1", "f239"), ("f240", "1"), ("1", "f241"), ("f223", "1"), ("f242", "f243"), ("1", "f236"), ("f245", "1"), ("1", "f246"), ("f244", "1"), ("f247", "f248")],
        },
        ParametricChain {
            variables: &["a11", "a12", "a13", "a21", "a22", "a23", "a31", "a32", "a33", "b11", "b12", "b13", "b21", "b22", "b23", "b31", "b32", "b33"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a11"), ("f4", "1"), ("1", "f5"), ("1", "b11"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "b11"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "a12"), ("f23", "1"), ("1", "f24"), ("1", "b21"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b21"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "a13"), ("f42", "1"), ("1", "f43"), ("1", "b31"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "b31"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f60"), ("f61", "1"), ("1", "f62"), ("f38", "1"), ("f63", "f64"), ("1", "f19"), ("f66", "1"), ("1", "f67"), ("f65", "1"), ("f68", "f69"), ("1", "1"), ("f71", "1"), ("1", "f72"), ("1", "f73"), ("f74", "1"), ("1", "f75"), ("f57", "1"), ("f76", "f77"), ("1", "f70"), ("f79", "1"), ("1", "f80"), ("f78", "1"), ("f81", "f82"), ("1", "1"), ("f84", "1"), ("1", "f85"), ("1", "a11"), ("f87", "1"), ("1", "f88"), ("1", "b12"), ("f90", "1"), ("1", "f91"), ("1", "f86"), ("f93", "1"), ("1", "f94"), ("f95", "b12"), ("1", "f89"), ("f97", "1"), ("1", "f98"), ("f96", "1"), ("f99", "f100"), ("f101", "1"), ("1", "1"), ("f103", "1"), ("1", "f104"), ("1", "a12"), ("f106", "1"), ("1", "f107"), ("1", "b22"), ("f109", "1"), ("1", "f110"), ("1", "f105"), ("f112", "1"), ("1", "f113"), ("f114", "b22"), ("1", "f108"), ("f116", "1"), ("1", "f117"), ("f115", "1"), ("f118", "f119"), ("f120", "1"), ("1", "1"), ("f122", "1"), ("1", "f123"), ("1", "a13"), ("f125", "1"), ("1", "f126"), ("1", "b32"), ("f128", "1"), ("1", "f129"), ("1", "f124"), ("f131", "1"), ("1", "f132"), ("f133", "b32"), ("1", "f127"), ("f135", "1"), ("1", "f136"), ("f134", "1"), ("f137", "f138"), ("f139", "1"), ("1", "1"), ("f141", "1"), ("1", "f142"), ("1", "f143"), ("f144", "1"), ("1", "f145"), ("f121", "1"), ("f146", "f147"), ("1", "f102"), ("f149", "1"), ("1", "f150"), ("f148", "1"), ("f151", "f152"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "f156"), ("f157", "1"), ("1", "f158"), ("f140", "1"), ("f159", "f160"), ("1", "f153"), ("f162", "1"), ("1", "f163"), ("f161", "1"), ("f164", "f165"), ("1", "1"), ("f167", "1"), ("1", "f168"), ("1", "a11"), ("f170", "1"), ("1", "f171"), ("1", "b13"), ("f173", "1"), ("1", "f174"), ("1", "f169"), ("f176", "1"), ("1", "f177"), ("f178", "b13"), ("1", "f172"), ("f180", "1"), ("1", "f181"), ("f179", "1"), ("f182", "f183"), ("f184", "1"), ("1", "1"), ("f186", "1"), ("1", "f187"), ("1", "a12"), ("f189", "1"), ("1", "f190"), ("1", "b23"), ("f192", "1"), ("1", "f193"), ("1", "f188"), ("f195", "1"), ("1", "f196"), ("f197", "b23"), ("1", "f191"), ("f199", "1"), ("1", "f200"), ("f198", "1"), ("f201", "f202"), ("f203", "1"), ("1", "1"), ("f205", "1"), ("1", "f206"), ("1", "a13"), ("f208", "1"), ("1", "f209"), ("1", "b33"), ("f211", "1"), ("1", "f212"), ("1", "f207"), ("f214", "1"), ("1", "f215"), ("f216", "b33"), ("1", "f210"), ("f218", "1"), ("1", "f219"), ("f217", "1"), ("f220", "f221"), ("f222", "1"), ("1", "1"), ("f224", "1"), ("1", "f225"), ("1", "f226"), ("f227", "1"), ("1", "f228"), ("f204", "1"), ("f229", "f230"), ("1", "f185"), ("f232", "1"), ("1", "f233"), ("f231", "1"), ("f234", "f235"), ("1", "1"), ("f237", "1"), ("1", "f238"), ("1", "f239"), ("f240", "1"), ("1", "f241"), ("f223", "1"), ("f242", "f243"), ("1", "f236"), ("f245", "1"), ("1", "f246"), ("f244", "1"), ("f247", "f248"), ("1", "1"), ("f250", "1"), ("1", "f251"), ("1", "a21"), ("f253", "1"), ("1", "f254"), ("1", "b11"), ("f256", "1"), ("1", "f257"), ("1", "f252"), ("f259", "1"), ("1", "f260"), ("f261", "b11"), ("1", "f255"), ("f263", "1"), ("1", "f264"), ("f262", "1"), ("f265", "f266"), ("f267", "1"), ("1", "1"), ("f269", "1"), ("1", "f270"), ("1", "a22"), ("f272", "1"), ("1", "f273"), ("1", "b21"), ("f275", "1"), ("1", "f276"), ("1", "f271"), ("f278", "1"), ("1", "f279"), ("f280", "b21"), ("1", "f274"), ("f282", "1"), ("1", "f283"), ("f281", "1"), ("f284", "f285"), ("f286", "1"), ("1", "1"), ("f288", "1"), ("1", "f289"), ("1", "a23"), ("f291", "1"), ("1", "f292"), ("1", "b31"), ("f294", "1"), ("1", "f295"), ("1", "f290"), ("f297", "1"), ("1", "f298"), ("f299", "b31"), ("1", "f293"), ("f301", "1"), ("1", "f302"), ("f300", "1"), ("f303", "f304"), ("f305", "1"), ("1", "1"), ("f307", "1"), ("1", "f308"), ("1", "f309"), ("f310", "1"), ("1", "f311"), ("f287", "1"), ("f312", "f313"), ("1", "f268"), ("f315", "1"), ("1", "f316"), ("f314", "1"), ("f317", "f318"), ("1", "1"), ("f320", "1"), ("1", "f321"), ("1", "f322"), ("f323", "1"), ("1", "f324"), ("f306", "1"), ("f325", "f326"), ("1", "f319"), ("f328", "1"), ("1", "f329"), ("f327", "1"), ("f330", "f331")],
        },
        ParametricChain {
            variables: &["a11", "a12", "a13", "a21", "a22", "a23", "a31", "a32", "a33", "b11", "b12", "b13", "b21", "b22", "b23", "b31", "b32", "b33"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a11"), ("f4", "1"), ("1", "f5"), ("1", "b11"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "b11"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "a12"), ("f23", "1"), ("1", "f24"), ("1", "b21"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b21"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "a13"), ("f42", "1"), ("1", "f43"), ("1", "b31"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "b31"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f60"), ("f61", "1"), ("1", "f62"), ("f38", "1"), ("f63", "f64"), ("1", "f19"), ("f66", "1"), ("1", "f67"), ("f65", "1"), ("f68", "f69"), ("1", "1"), ("f71", "1"), ("1", "f72"), ("1", "f73"), ("f74", "1"), ("1", "f75"), ("f57", "1"), ("f76", "f77"), ("1", "f70"), ("f79", "1"), ("1", "f80"), ("f78", "1"), ("f81", "f82"), ("1", "1"), ("f84", "1"), ("1", "f85"), ("1", "a11"), ("f87", "1"), ("1", "f88"), ("1", "b12"), ("f90", "1"), ("1", "f91"), ("1", "f86"), ("f93", "1"), ("1", "f94"), ("f95", "b12"), ("1", "f89"), ("f97", "1"), ("1", "f98"), ("f96", "1"), ("f99", "f100"), ("f101", "1"), ("1", "1"), ("f103", "1"), ("1", "f104"), ("1", "a12"), ("f106", "1"), ("1", "f107"), ("1", "b22"), ("f109", "1"), ("1", "f110"), ("1", "f105"), ("f112", "1"), ("1", "f113"), ("f114", "b22"), ("1", "f108"), ("f116", "1"), ("1", "f117"), ("f115", "1"), ("f118", "f119"), ("f120", "1"), ("1", "1"), ("f122", "1"), ("1", "f123"), ("1", "a13"), ("f125", "1"), ("1", "f126"), ("1", "b32"), ("f128", "1"), ("1", "f129"), ("1", "f124"), ("f131", "1"), ("1", "f132"), ("f133", "b32"), ("1", "f127"), ("f135", "1"), ("1", "f136"), ("f134", "1"), ("f137", "f138"), ("f139", "1"), ("1", "1"), ("f141", "1"), ("1", "f142"), ("1", "f143"), ("f144", "1"), ("1", "f145"), ("f121", "1"), ("f146", "f147"), ("1", "f102"), ("f149", "1"), ("1", "f150"), ("f148", "1"), ("f151", "f152"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "f156"), ("f157", "1"), ("1", "f158"), ("f140", "1"), ("f159", "f160"), ("1", "f153"), ("f162", "1"), ("1", "f163"), ("f161", "1"), ("f164", "f165"), ("1", "1"), ("f167", "1"), ("1", "f168"), ("1", "a11"), ("f170", "1"), ("1", "f171"), ("1", "b13"), ("f173", "1"), ("1", "f174"), ("1", "f169"), ("f176", "1"), ("1", "f177"), ("f178", "b13"), ("1", "f172"), ("f180", "1"), ("1", "f181"), ("f179", "1"), ("f182", "f183"), ("f184", "1"), ("1", "1"), ("f186", "1"), ("1", "f187"), ("1", "a12"), ("f189", "1"), ("1", "f190"), ("1", "b23"), ("f192", "1"), ("1", "f193"), ("1", "f188"), ("f195", "1"), ("1", "f196"), ("f197", "b23"), ("1", "f191"), ("f199", "1"), ("1", "f200"), ("f198", "1"), ("f201", "f202"), ("f203", "1"), ("1", "1"), ("f205", "1"), ("1", "f206"), ("1", "a13"), ("f208", "1"), ("1", "f209"), ("1", "b33"), ("f211", "1"), ("1", "f212"), ("1", "f207"), ("f214", "1"), ("1", "f215"), ("f216", "b33"), ("1", "f210"), ("f218", "1"), ("1", "f219"), ("f217", "1"), ("f220", "f221"), ("f222", "1"), ("1", "1"), ("f224", "1"), ("1", "f225"), ("1", "f226"), ("f227", "1"), ("1", "f228"), ("f204", "1"), ("f229", "f230"), ("1", "f185"), ("f232", "1"), ("1", "f233"), ("f231", "1"), ("f234", "f235"), ("1", "1"), ("f237", "1"), ("1", "f238"), ("1", "f239"), ("f240", "1"), ("1", "f241"), ("f223", "1"), ("f242", "f243"), ("1", "f236"), ("f245", "1"), ("1", "f246"), ("f244", "1"), ("f247", "f248"), ("1", "1"), ("f250", "1"), ("1", "f251"), ("1", "a21"), ("f253", "1"), ("1", "f254"), ("1", "b11"), ("f256", "1"), ("1", "f257"), ("1", "f252"), ("f259", "1"), ("1", "f260"), ("f261", "b11"), ("1", "f255"), ("f263", "1"), ("1", "f264"), ("f262", "1"), ("f265", "f266"), ("f267", "1"), ("1", "1"), ("f269", "1"), ("1", "f270"), ("1", "a22"), ("f272", "1"), ("1", "f273"), ("1", "b21"), ("f275", "1"), ("1", "f276"), ("1", "f271"), ("f278", "1"), ("1", "f279"), ("f280", "b21"), ("1", "f274"), ("f282", "1"), ("1", "f283"), ("f281", "1"), ("f284", "f285"), ("f286", "1"), ("1", "1"), ("f288", "1"), ("1", "f289"), ("1", "a23"), ("f291", "1"), ("1", "f292"), ("1", "b31"), ("f294", "1"), ("1", "f295"), ("1", "f290"), ("f297", "1"), ("1", "f298"), ("f299", "b31"), ("1", "f293"), ("f301", "1"), ("1", "f302"), ("f300", "1"), ("f303", "f304"), ("f305", "1"), ("1", "1"), ("f307", "1"), ("1", "f308"), ("1", "f309"), ("f310", "1"), ("1", "f311"), ("f287", "1"), ("f312", "f313"), ("1", "f268"), ("f315", "1"), ("1", "f316"), ("f314", "1"), ("f317", "f318"), ("1", "1"), ("f320", "1"), ("1", "f321"), ("1", "f322"), ("f323", "1"), ("1", "f324"), ("f306", "1"), ("f325", "f326"), ("1", "f319"), ("f328", "1"), ("1", "f329"), ("f327", "1"), ("f330", "f331"), ("1", "1"), ("f333", "1"), ("1", "f334"), ("1", "a21"), ("f336", "1"), ("1", "f337"), ("1", "b12"), ("f339", "1"), ("1", "f340"), ("1", "f335"), ("f342", "1"), ("1", "f343"), ("f344", "b12"), ("1", "f338"), ("f346", "1"), ("1", "f347"), ("f345", "1"), ("f348", "f349"), ("f350", "1"), ("1", "1"), ("f352", "1"), ("1", "f353"), ("1", "a22"), ("f355", "1"), ("1", "f356"), ("1", "b22"), ("f358", "1"), ("1", "f359"), ("1", "f354"), ("f361", "1"), ("1", "f362"), ("f363", "b22"), ("1", "f357"), ("f365", "1"), ("1", "f366"), ("f364", "1"), ("f367", "f368"), ("f369", "1"), ("1", "1"), ("f371", "1"), ("1", "f372"), ("1", "a23"), ("f374", "1"), ("1", "f375"), ("1", "b32"), ("f377", "1"), ("1", "f378"), ("1", "f373"), ("f380", "1"), ("1", "f381"), ("f382", "b32"), ("1", "f376"), ("f384", "1"), ("1", "f385"), ("f383", "1"), ("f386", "f387"), ("f388", "1"), ("1", "1"), ("f390", "1"), ("1", "f391"), ("1", "f392"), ("f393", "1"), ("1", "f394"), ("f370", "1"), ("f395", "f396"), ("1", "f351"), ("f398", "1"), ("1", "f399"), ("f397", "1"), ("f400", "f401"), ("1", "1"), ("f403", "1"), ("1", "f404"), ("1", "f405"), ("f406", "1"), ("1", "f407"), ("f389", "1"), ("f408", "f409"), ("1", "f402"), ("f411", "1"), ("1", "f412"), ("f410", "1"), ("f413", "f414")],
        },
        ParametricChain {
            variables: &["a11", "a12", "a13", "a21", "a22", "a23", "a31", "a32", "a33", "b11", "b12", "b13", "b21", "b22", "b23", "b31", "b32", "b33"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a11"), ("f4", "1"), ("1", "f5"), ("1", "b11"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "b11"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "a12"), ("f23", "1"), ("1", "f24"), ("1", "b21"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b21"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "a13"), ("f42", "1"), ("1", "f43"), ("1", "b31"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "b31"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f60"), ("f61", "1"), ("1", "f62"), ("f38", "1"), ("f63", "f64"), ("1", "f19"), ("f66", "1"), ("1", "f67"), ("f65", "1"), ("f68", "f69"), ("1", "1"), ("f71", "1"), ("1", "f72"), ("1", "f73"), ("f74", "1"), ("1", "f75"), ("f57", "1"), ("f76", "f77"), ("1", "f70"), ("f79", "1"), ("1", "f80"), ("f78", "1"), ("f81", "f82"), ("1", "1"), ("f84", "1"), ("1", "f85"), ("1", "a11"), ("f87", "1"), ("1", "f88"), ("1", "b12"), ("f90", "1"), ("1", "f91"), ("1", "f86"), ("f93", "1"), ("1", "f94"), ("f95", "b12"), ("1", "f89"), ("f97", "1"), ("1", "f98"), ("f96", "1"), ("f99", "f100"), ("f101", "1"), ("1", "1"), ("f103", "1"), ("1", "f104"), ("1", "a12"), ("f106", "1"), ("1", "f107"), ("1", "b22"), ("f109", "1"), ("1", "f110"), ("1", "f105"), ("f112", "1"), ("1", "f113"), ("f114", "b22"), ("1", "f108"), ("f116", "1"), ("1", "f117"), ("f115", "1"), ("f118", "f119"), ("f120", "1"), ("1", "1"), ("f122", "1"), ("1", "f123"), ("1", "a13"), ("f125", "1"), ("1", "f126"), ("1", "b32"), ("f128", "1"), ("1", "f129"), ("1", "f124"), ("f131", "1"), ("1", "f132"), ("f133", "b32"), ("1", "f127"), ("f135", "1"), ("1", "f136"), ("f134", "1"), ("f137", "f138"), ("f139", "1"), ("1", "1"), ("f141", "1"), ("1", "f142"), ("1", "f143"), ("f144", "1"), ("1", "f145"), ("f121", "1"), ("f146", "f147"), ("1", "f102"), ("f149", "1"), ("1", "f150"), ("f148", "1"), ("f151", "f152"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "f156"), ("f157", "1"), ("1", "f158"), ("f140", "1"), ("f159", "f160"), ("1", "f153"), ("f162", "1"), ("1", "f163"), ("f161", "1"), ("f164", "f165"), ("1", "1"), ("f167", "1"), ("1", "f168"), ("1", "a11"), ("f170", "1"), ("1", "f171"), ("1", "b13"), ("f173", "1"), ("1", "f174"), ("1", "f169"), ("f176", "1"), ("1", "f177"), ("f178", "b13"), ("1", "f172"), ("f180", "1"), ("1", "f181"), ("f179", "1"), ("f182", "f183"), ("f184", "1"), ("1", "1"), ("f186", "1"), ("1", "f187"), ("1", "a12"), ("f189", "1"), ("1", "f190"), ("1", "b23"), ("f192", "1"), ("1", "f193"), ("1", "f188"), ("f195", "1"), ("1", "f196"), ("f197", "b23"), ("1", "f191"), ("f199", "1"), ("1", "f200"), ("f198", "1"), ("f201", "f202"), ("f203", "1"), ("1", "1"), ("f205", "1"), ("1", "f206"), ("1", "a13"), ("f208", "1"), ("1", "f209"), ("1", "b33"), ("f211", "1"), ("1", "f212"), ("1", "f207"), ("f214", "1"), ("1", "f215"), ("f216", "b33"), ("1", "f210"), ("f218", "1"), ("1", "f219"), ("f217", "1"), ("f220", "f221"), ("f222", "1"), ("1", "1"), ("f224", "1"), ("1", "f225"), ("1", "f226"), ("f227", "1"), ("1", "f228"), ("f204", "1"), ("f229", "f230"), ("1", "f185"), ("f232", "1"), ("1", "f233"), ("f231", "1"), ("f234", "f235"), ("1", "1"), ("f237", "1"), ("1", "f238"), ("1", "f239"), ("f240", "1"), ("1", "f241"), ("f223", "1"), ("f242", "f243"), ("1", "f236"), ("f245", "1"), ("1", "f246"), ("f244", "1"), ("f247", "f248"), ("1", "1"), ("f250", "1"), ("1", "f251"), ("1", "a21"), ("f253", "1"), ("1", "f254"), ("1", "b11"), ("f256", "1"), ("1", "f257"), ("1", "f252"), ("f259", "1"), ("1", "f260"), ("f261", "b11"), ("1", "f255"), ("f263", "1"), ("1", "f264"), ("f262", "1"), ("f265", "f266"), ("f267", "1"), ("1", "1"), ("f269", "1"), ("1", "f270"), ("1", "a22"), ("f272", "1"), ("1", "f273"), ("1", "b21"), ("f275", "1"), ("1", "f276"), ("1", "f271"), ("f278", "1"), ("1", "f279"), ("f280", "b21"), ("1", "f274"), ("f282", "1"), ("1", "f283"), ("f281", "1"), ("f284", "f285"), ("f286", "1"), ("1", "1"), ("f288", "1"), ("1", "f289"), ("1", "a23"), ("f291", "1"), ("1", "f292"), ("1", "b31"), ("f294", "1"), ("1", "f295"), ("1", "f290"), ("f297", "1"), ("1", "f298"), ("f299", "b31"), ("1", "f293"), ("f301", "1"), ("1", "f302"), ("f300", "1"), ("f303", "f304"), ("f305", "1"), ("1", "1"), ("f307", "1"), ("1", "f308"), ("1", "f309"), ("f310", "1"), ("1", "f311"), ("f287", "1"), ("f312", "f313"), ("1", "f268"), ("f315", "1"), ("1", "f316"), ("f314", "1"), ("f317", "f318"), ("1", "1"), ("f320", "1"), ("1", "f321"), ("1", "f322"), ("f323", "1"), ("1", "f324"), ("f306", "1"), ("f325", "f326"), ("1", "f319"), ("f328", "1"), ("1", "f329"), ("f327", "1"), ("f330", "f331"), ("1", "1"), ("f333", "1"), ("1", "f334"), ("1", "a21"), ("f336", "1"), ("1", "f337"), ("1", "b12"), ("f339", "1"), ("1", "f340"), ("1", "f335"), ("f342", "1"), ("1", "f343"), ("f344", "b12"), ("1", "f338"), ("f346", "1"), ("1", "f347"), ("f345", "1"), ("f348", "f349"), ("f350", "1"), ("1", "1"), ("f352", "1"), ("1", "f353"), ("1", "a22"), ("f355", "1"), ("1", "f356"), ("1", "b22"), ("f358", "1"), ("1", "f359"), ("1", "f354"), ("f361", "1"), ("1", "f362"), ("f363", "b22"), ("1", "f357"), ("f365", "1"), ("1", "f366"), ("f364", "1"), ("f367", "f368"), ("f369", "1"), ("1", "1"), ("f371", "1"), ("1", "f372"), ("1", "a23"), ("f374", "1"), ("1", "f375"), ("1", "b32"), ("f377", "1"), ("1", "f378"), ("1", "f373"), ("f380", "1"), ("1", "f381"), ("f382", "b32"), ("1", "f376"), ("f384", "1"), ("1", "f385"), ("f383", "1"), ("f386", "f387"), ("f388", "1"), ("1", "1"), ("f390", "1"), ("1", "f391"), ("1", "f392"), ("f393", "1"), ("1", "f394"), ("f370", "1"), ("f395", "f396"), ("1", "f351"), ("f398", "1"), ("1", "f399"), ("f397", "1"), ("f400", "f401"), ("1", "1"), ("f403", "1"), ("1", "f404"), ("1", "f405"), ("f406", "1"), ("1", "f407"), ("f389", "1"), ("f408", "f409"), ("1", "f402"), ("f411", "1"), ("1", "f412"), ("f410", "1"), ("f413", "f414"), ("1", "1"), ("f416", "1"), ("1", "f417"), ("1", "a21"), ("f419", "1"), ("1", "f420"), ("1", "b13"), ("f422", "1"), ("1", "f423"), ("1", "f418"), ("f425", "1"), ("1", "f426"), ("f427", "b13"), ("1", "f421"), ("f429", "1"), ("1", "f430"), ("f428", "1"), ("f431", "f432"), ("f433", "1"), ("1", "1"), ("f435", "1"), ("1", "f436"), ("1", "a22"), ("f438", "1"), ("1", "f439"), ("1", "b23"), ("f441", "1"), ("1", "f442"), ("1", "f437"), ("f444", "1"), ("1", "f445"), ("f446", "b23"), ("1", "f440"), ("f448", "1"), ("1", "f449"), ("f447", "1"), ("f450", "f451"), ("f452", "1"), ("1", "1"), ("f454", "1"), ("1", "f455"), ("1", "a23"), ("f457", "1"), ("1", "f458"), ("1", "b33"), ("f460", "1"), ("1", "f461"), ("1", "f456"), ("f463", "1"), ("1", "f464"), ("f465", "b33"), ("1", "f459"), ("f467", "1"), ("1", "f468"), ("f466", "1"), ("f469", "f470"), ("f471", "1"), ("1", "1"), ("f473", "1"), ("1", "f474"), ("1", "f475"), ("f476", "1"), ("1", "f477"), ("f453", "1"), ("f478", "f479"), ("1", "f434"), ("f481", "1"), ("1", "f482"), ("f480", "1"), ("f483", "f484"), ("1", "1"), ("f486", "1"), ("1", "f487"), ("1", "f488"), ("f489", "1"), ("1", "f490"), ("f472", "1"), ("f491", "f492"), ("1", "f485"), ("f494", "1"), ("1", "f495"), ("f493", "1"), ("f496", "f497")],
        },
        ParametricChain {
            variables: &["a11", "a12", "a13", "a21", "a22", "a23", "a31", "a32", "a33", "b11", "b12", "b13", "b21", "b22", "b23", "b31", "b32", "b33"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a11"), ("f4", "1"), ("1", "f5"), ("1", "b11"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "b11"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "a12"), ("f23", "1"), ("1", "f24"), ("1", "b21"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b21"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "a13"), ("f42", "1"), ("1", "f43"), ("1", "b31"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "b31"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f60"), ("f61", "1"), ("1", "f62"), ("f38", "1"), ("f63", "f64"), ("1", "f19"), ("f66", "1"), ("1", "f67"), ("f65", "1"), ("f68", "f69"), ("1", "1"), ("f71", "1"), ("1", "f72"), ("1", "f73"), ("f74", "1"), ("1", "f75"), ("f57", "1"), ("f76", "f77"), ("1", "f70"), ("f79", "1"), ("1", "f80"), ("f78", "1"), ("f81", "f82"), ("1", "1"), ("f84", "1"), ("1", "f85"), ("1", "a11"), ("f87", "1"), ("1", "f88"), ("1", "b12"), ("f90", "1"), ("1", "f91"), ("1", "f86"), ("f93", "1"), ("1", "f94"), ("f95", "b12"), ("1", "f89"), ("f97", "1"), ("1", "f98"), ("f96", "1"), ("f99", "f100"), ("f101", "1"), ("1", "1"), ("f103", "1"), ("1", "f104"), ("1", "a12"), ("f106", "1"), ("1", "f107"), ("1", "b22"), ("f109", "1"), ("1", "f110"), ("1", "f105"), ("f112", "1"), ("1", "f113"), ("f114", "b22"), ("1", "f108"), ("f116", "1"), ("1", "f117"), ("f115", "1"), ("f118", "f119"), ("f120", "1"), ("1", "1"), ("f122", "1"), ("1", "f123"), ("1", "a13"), ("f125", "1"), ("1", "f126"), ("1", "b32"), ("f128", "1"), ("1", "f129"), ("1", "f124"), ("f131", "1"), ("1", "f132"), ("f133", "b32"), ("1", "f127"), ("f135", "1"), ("1", "f136"), ("f134", "1"), ("f137", "f138"), ("f139", "1"), ("1", "1"), ("f141", "1"), ("1", "f142"), ("1", "f143"), ("f144", "1"), ("1", "f145"), ("f121", "1"), ("f146", "f147"), ("1", "f102"), ("f149", "1"), ("1", "f150"), ("f148", "1"), ("f151", "f152"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "f156"), ("f157", "1"), ("1", "f158"), ("f140", "1"), ("f159", "f160"), ("1", "f153"), ("f162", "1"), ("1", "f163"), ("f161", "1"), ("f164", "f165"), ("1", "1"), ("f167", "1"), ("1", "f168"), ("1", "a11"), ("f170", "1"), ("1", "f171"), ("1", "b13"), ("f173", "1"), ("1", "f174"), ("1", "f169"), ("f176", "1"), ("1", "f177"), ("f178", "b13"), ("1", "f172"), ("f180", "1"), ("1", "f181"), ("f179", "1"), ("f182", "f183"), ("f184", "1"), ("1", "1"), ("f186", "1"), ("1", "f187"), ("1", "a12"), ("f189", "1"), ("1", "f190"), ("1", "b23"), ("f192", "1"), ("1", "f193"), ("1", "f188"), ("f195", "1"), ("1", "f196"), ("f197", "b23"), ("1", "f191"), ("f199", "1"), ("1", "f200"), ("f198", "1"), ("f201", "f202"), ("f203", "1"), ("1", "1"), ("f205", "1"), ("1", "f206"), ("1", "a13"), ("f208", "1"), ("1", "f209"), ("1", "b33"), ("f211", "1"), ("1", "f212"), ("1", "f207"), ("f214", "1"), ("1", "f215"), ("f216", "b33"), ("1", "f210"), ("f218", "1"), ("1", "f219"), ("f217", "1"), ("f220", "f221"), ("f222", "1"), ("1", "1"), ("f224", "1"), ("1", "f225"), ("1", "f226"), ("f227", "1"), ("1", "f228"), ("f204", "1"), ("f229", "f230"), ("1", "f185"), ("f232", "1"), ("1", "f233"), ("f231", "1"), ("f234", "f235"), ("1", "1"), ("f237", "1"), ("1", "f238"), ("1", "f239"), ("f240", "1"), ("1", "f241"), ("f223", "1"), ("f242", "f243"), ("1", "f236"), ("f245", "1"), ("1", "f246"), ("f244", "1"), ("f247", "f248"), ("1", "1"), ("f250", "1"), ("1", "f251"), ("1", "a21"), ("f253", "1"), ("1", "f254"), ("1", "b11"), ("f256", "1"), ("1", "f257"), ("1", "f252"), ("f259", "1"), ("1", "f260"), ("f261", "b11"), ("1", "f255"), ("f263", "1"), ("1", "f264"), ("f262", "1"), ("f265", "f266"), ("f267", "1"), ("1", "1"), ("f269", "1"), ("1", "f270"), ("1", "a22"), ("f272", "1"), ("1", "f273"), ("1", "b21"), ("f275", "1"), ("1", "f276"), ("1", "f271"), ("f278", "1"), ("1", "f279"), ("f280", "b21"), ("1", "f274"), ("f282", "1"), ("1", "f283"), ("f281", "1"), ("f284", "f285"), ("f286", "1"), ("1", "1"), ("f288", "1"), ("1", "f289"), ("1", "a23"), ("f291", "1"), ("1", "f292"), ("1", "b31"), ("f294", "1"), ("1", "f295"), ("1", "f290"), ("f297", "1"), ("1", "f298"), ("f299", "b31"), ("1", "f293"), ("f301", "1"), ("1", "f302"), ("f300", "1"), ("f303", "f304"), ("f305", "1"), ("1", "1"), ("f307", "1"), ("1", "f308"), ("1", "f309"), ("f310", "1"), ("1", "f311"), ("f287", "1"), ("f312", "f313"), ("1", "f268"), ("f315", "1"), ("1", "f316"), ("f314", "1"), ("f317", "f318"), ("1", "1"), ("f320", "1"), ("1", "f321"), ("1", "f322"), ("f323", "1"), ("1", "f324"), ("f306", "1"), ("f325", "f326"), ("1", "f319"), ("f328", "1"), ("1", "f329"), ("f327", "1"), ("f330", "f331"), ("1", "1"), ("f333", "1"), ("1", "f334"), ("1", "a21"), ("f336", "1"), ("1", "f337"), ("1", "b12"), ("f339", "1"), ("1", "f340"), ("1", "f335"), ("f342", "1"), ("1", "f343"), ("f344", "b12"), ("1", "f338"), ("f346", "1"), ("1", "f347"), ("f345", "1"), ("f348", "f349"), ("f350", "1"), ("1", "1"), ("f352", "1"), ("1", "f353"), ("1", "a22"), ("f355", "1"), ("1", "f356"), ("1", "b22"), ("f358", "1"), ("1", "f359"), ("1", "f354"), ("f361", "1"), ("1", "f362"), ("f363", "b22"), ("1", "f357"), ("f365", "1"), ("1", "f366"), ("f364", "1"), ("f367", "f368"), ("f369", "1"), ("1", "1"), ("f371", "1"), ("1", "f372"), ("1", "a23"), ("f374", "1"), ("1", "f375"), ("1", "b32"), ("f377", "1"), ("1", "f378"), ("1", "f373"), ("f380", "1"), ("1", "f381"), ("f382", "b32"), ("1", "f376"), ("f384", "1"), ("1", "f385"), ("f383", "1"), ("f386", "f387"), ("f388", "1"), ("1", "1"), ("f390", "1"), ("1", "f391"), ("1", "f392"), ("f393", "1"), ("1", "f394"), ("f370", "1"), ("f395", "f396"), ("1", "f351"), ("f398", "1"), ("1", "f399"), ("f397", "1"), ("f400", "f401"), ("1", "1"), ("f403", "1"), ("1", "f404"), ("1", "f405"), ("f406", "1"), ("1", "f407"), ("f389", "1"), ("f408", "f409"), ("1", "f402"), ("f411", "1"), ("1", "f412"), ("f410", "1"), ("f413", "f414"), ("1", "1"), ("f416", "1"), ("1", "f417"), ("1", "a21"), ("f419", "1"), ("1", "f420"), ("1", "b13"), ("f422", "1"), ("1", "f423"), ("1", "f418"), ("f425", "1"), ("1", "f426"), ("f427", "b13"), ("1", "f421"), ("f429", "1"), ("1", "f430"), ("f428", "1"), ("f431", "f432"), ("f433", "1"), ("1", "1"), ("f435", "1"), ("1", "f436"), ("1", "a22"), ("f438", "1"), ("1", "f439"), ("1", "b23"), ("f441", "1"), ("1", "f442"), ("1", "f437"), ("f444", "1"), ("1", "f445"), ("f446", "b23"), ("1", "f440"), ("f448", "1"), ("1", "f449"), ("f447", "1"), ("f450", "f451"), ("f452", "1"), ("1", "1"), ("f454", "1"), ("1", "f455"), ("1", "a23"), ("f457", "1"), ("1", "f458"), ("1", "b33"), ("f460", "1"), ("1", "f461"), ("1", "f456"), ("f463", "1"), ("1", "f464"), ("f465", "b33"), ("1", "f459"), ("f467", "1"), ("1", "f468"), ("f466", "1"), ("f469", "f470"), ("f471", "1"), ("1", "1"), ("f473", "1"), ("1", "f474"), ("1", "f475"), ("f476", "1"), ("1", "f477"), ("f453", "1"), ("f478", "f479"), ("1", "f434"), ("f481", "1"), ("1", "f482"), ("f480", "1"), ("f483", "f484"), ("1", "1"), ("f486", "1"), ("1", "f487"), ("1", "f488"), ("f489", "1"), ("1", "f490"), ("f472", "1"), ("f491", "f492"), ("1", "f485"), ("f494", "1"), ("1", "f495"), ("f493", "1"), ("f496", "f497"), ("1", "1"), ("f499", "1"), ("1", "f500"), ("1", "a31"), ("f502", "1"), ("1", "f503"), ("1", "b11"), ("f505", "1"), ("1", "f506"), ("1", "f501"), ("f508", "1"), ("1", "f509"), ("f510", "b11"), ("1", "f504"), ("f512", "1"), ("1", "f513"), ("f511", "1"), ("f514", "f515"), ("f516", "1"), ("1", "1"), ("f518", "1"), ("1", "f519"), ("1", "a32"), ("f521", "1"), ("1", "f522"), ("1", "b21"), ("f524", "1"), ("1", "f525"), ("1", "f520"), ("f527", "1"), ("1", "f528"), ("f529", "b21"), ("1", "f523"), ("f531", "1"), ("1", "f532"), ("f530", "1"), ("f533", "f534"), ("f535", "1"), ("1", "1"), ("f537", "1"), ("1", "f538"), ("1", "a33"), ("f540", "1"), ("1", "f541"), ("1", "b31"), ("f543", "1"), ("1", "f544"), ("1", "f539"), ("f546", "1"), ("1", "f547"), ("f548", "b31"), ("1", "f542"), ("f550", "1"), ("1", "f551"), ("f549", "1"), ("f552", "f553"), ("f554", "1"), ("1", "1"), ("f556", "1"), ("1", "f557"), ("1", "f558"), ("f559", "1"), ("1", "f560"), ("f536", "1"), ("f561", "f562"), ("1", "f517"), ("f564", "1"), ("1", "f565"), ("f563", "1"), ("f566", "f567"), ("1", "1"), ("f569", "1"), ("1", "f570"), ("1", "f571"), ("f572", "1"), ("1", "f573"), ("f555", "1"), ("f574", "f575"), ("1", "f568"), ("f577", "1"), ("1", "f578"), ("f576", "1"), ("f579", "f580")],
        },
        ParametricChain {
            variables: &["a11", "a12", "a13", "a21", "a22", "a23", "a31", "a32", "a33", "b11", "b12", "b13", "b21", "b22", "b23", "b31", "b32", "b33"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a11"), ("f4", "1"), ("1", "f5"), ("1", "b11"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "b11"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "a12"), ("f23", "1"), ("1", "f24"), ("1", "b21"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b21"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "a13"), ("f42", "1"), ("1", "f43"), ("1", "b31"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "b31"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f60"), ("f61", "1"), ("1", "f62"), ("f38", "1"), ("f63", "f64"), ("1", "f19"), ("f66", "1"), ("1", "f67"), ("f65", "1"), ("f68", "f69"), ("1", "1"), ("f71", "1"), ("1", "f72"), ("1", "f73"), ("f74", "1"), ("1", "f75"), ("f57", "1"), ("f76", "f77"), ("1", "f70"), ("f79", "1"), ("1", "f80"), ("f78", "1"), ("f81", "f82"), ("1", "1"), ("f84", "1"), ("1", "f85"), ("1", "a11"), ("f87", "1"), ("1", "f88"), ("1", "b12"), ("f90", "1"), ("1", "f91"), ("1", "f86"), ("f93", "1"), ("1", "f94"), ("f95", "b12"), ("1", "f89"), ("f97", "1"), ("1", "f98"), ("f96", "1"), ("f99", "f100"), ("f101", "1"), ("1", "1"), ("f103", "1"), ("1", "f104"), ("1", "a12"), ("f106", "1"), ("1", "f107"), ("1", "b22"), ("f109", "1"), ("1", "f110"), ("1", "f105"), ("f112", "1"), ("1", "f113"), ("f114", "b22"), ("1", "f108"), ("f116", "1"), ("1", "f117"), ("f115", "1"), ("f118", "f119"), ("f120", "1"), ("1", "1"), ("f122", "1"), ("1", "f123"), ("1", "a13"), ("f125", "1"), ("1", "f126"), ("1", "b32"), ("f128", "1"), ("1", "f129"), ("1", "f124"), ("f131", "1"), ("1", "f132"), ("f133", "b32"), ("1", "f127"), ("f135", "1"), ("1", "f136"), ("f134", "1"), ("f137", "f138"), ("f139", "1"), ("1", "1"), ("f141", "1"), ("1", "f142"), ("1", "f143"), ("f144", "1"), ("1", "f145"), ("f121", "1"), ("f146", "f147"), ("1", "f102"), ("f149", "1"), ("1", "f150"), ("f148", "1"), ("f151", "f152"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "f156"), ("f157", "1"), ("1", "f158"), ("f140", "1"), ("f159", "f160"), ("1", "f153"), ("f162", "1"), ("1", "f163"), ("f161", "1"), ("f164", "f165"), ("1", "1"), ("f167", "1"), ("1", "f168"), ("1", "a11"), ("f170", "1"), ("1", "f171"), ("1", "b13"), ("f173", "1"), ("1", "f174"), ("1", "f169"), ("f176", "1"), ("1", "f177"), ("f178", "b13"), ("1", "f172"), ("f180", "1"), ("1", "f181"), ("f179", "1"), ("f182", "f183"), ("f184", "1"), ("1", "1"), ("f186", "1"), ("1", "f187"), ("1", "a12"), ("f189", "1"), ("1", "f190"), ("1", "b23"), ("f192", "1"), ("1", "f193"), ("1", "f188"), ("f195", "1"), ("1", "f196"), ("f197", "b23"), ("1", "f191"), ("f199", "1"), ("1", "f200"), ("f198", "1"), ("f201", "f202"), ("f203", "1"), ("1", "1"), ("f205", "1"), ("1", "f206"), ("1", "a13"), ("f208", "1"), ("1", "f209"), ("1", "b33"), ("f211", "1"), ("1", "f212"), ("1", "f207"), ("f214", "1"), ("1", "f215"), ("f216", "b33"), ("1", "f210"), ("f218", "1"), ("1", "f219"), ("f217", "1"), ("f220", "f221"), ("f222", "1"), ("1", "1"), ("f224", "1"), ("1", "f225"), ("1", "f226"), ("f227", "1"), ("1", "f228"), ("f204", "1"), ("f229", "f230"), ("1", "f185"), ("f232", "1"), ("1", "f233"), ("f231", "1"), ("f234", "f235"), ("1", "1"), ("f237", "1"), ("1", "f238"), ("1", "f239"), ("f240", "1"), ("1", "f241"), ("f223", "1"), ("f242", "f243"), ("1", "f236"), ("f245", "1"), ("1", "f246"), ("f244", "1"), ("f247", "f248"), ("1", "1"), ("f250", "1"), ("1", "f251"), ("1", "a21"), ("f253", "1"), ("1", "f254"), ("1", "b11"), ("f256", "1"), ("1", "f257"), ("1", "f252"), ("f259", "1"), ("1", "f260"), ("f261", "b11"), ("1", "f255"), ("f263", "1"), ("1", "f264"), ("f262", "1"), ("f265", "f266"), ("f267", "1"), ("1", "1"), ("f269", "1"), ("1", "f270"), ("1", "a22"), ("f272", "1"), ("1", "f273"), ("1", "b21"), ("f275", "1"), ("1", "f276"), ("1", "f271"), ("f278", "1"), ("1", "f279"), ("f280", "b21"), ("1", "f274"), ("f282", "1"), ("1", "f283"), ("f281", "1"), ("f284", "f285"), ("f286", "1"), ("1", "1"), ("f288", "1"), ("1", "f289"), ("1", "a23"), ("f291", "1"), ("1", "f292"), ("1", "b31"), ("f294", "1"), ("1", "f295"), ("1", "f290"), ("f297", "1"), ("1", "f298"), ("f299", "b31"), ("1", "f293"), ("f301", "1"), ("1", "f302"), ("f300", "1"), ("f303", "f304"), ("f305", "1"), ("1", "1"), ("f307", "1"), ("1", "f308"), ("1", "f309"), ("f310", "1"), ("1", "f311"), ("f287", "1"), ("f312", "f313"), ("1", "f268"), ("f315", "1"), ("1", "f316"), ("f314", "1"), ("f317", "f318"), ("1", "1"), ("f320", "1"), ("1", "f321"), ("1", "f322"), ("f323", "1"), ("1", "f324"), ("f306", "1"), ("f325", "f326"), ("1", "f319"), ("f328", "1"), ("1", "f329"), ("f327", "1"), ("f330", "f331"), ("1", "1"), ("f333", "1"), ("1", "f334"), ("1", "a21"), ("f336", "1"), ("1", "f337"), ("1", "b12"), ("f339", "1"), ("1", "f340"), ("1", "f335"), ("f342", "1"), ("1", "f343"), ("f344", "b12"), ("1", "f338"), ("f346", "1"), ("1", "f347"), ("f345", "1"), ("f348", "f349"), ("f350", "1"), ("1", "1"), ("f352", "1"), ("1", "f353"), ("1", "a22"), ("f355", "1"), ("1", "f356"), ("1", "b22"), ("f358", "1"), ("1", "f359"), ("1", "f354"), ("f361", "1"), ("1", "f362"), ("f363", "b22"), ("1", "f357"), ("f365", "1"), ("1", "f366"), ("f364", "1"), ("f367", "f368"), ("f369", "1"), ("1", "1"), ("f371", "1"), ("1", "f372"), ("1", "a23"), ("f374", "1"), ("1", "f375"), ("1", "b32"), ("f377", "1"), ("1", "f378"), ("1", "f373"), ("f380", "1"), ("1", "f381"), ("f382", "b32"), ("1", "f376"), ("f384", "1"), ("1", "f385"), ("f383", "1"), ("f386", "f387"), ("f388", "1"), ("1", "1"), ("f390", "1"), ("1", "f391"), ("1", "f392"), ("f393", "1"), ("1", "f394"), ("f370", "1"), ("f395", "f396"), ("1", "f351"), ("f398", "1"), ("1", "f399"), ("f397", "1"), ("f400", "f401"), ("1", "1"), ("f403", "1"), ("1", "f404"), ("1", "f405"), ("f406", "1"), ("1", "f407"), ("f389", "1"), ("f408", "f409"), ("1", "f402"), ("f411", "1"), ("1", "f412"), ("f410", "1"), ("f413", "f414"), ("1", "1"), ("f416", "1"), ("1", "f417"), ("1", "a21"), ("f419", "1"), ("1", "f420"), ("1", "b13"), ("f422", "1"), ("1", "f423"), ("1", "f418"), ("f425", "1"), ("1", "f426"), ("f427", "b13"), ("1", "f421"), ("f429", "1"), ("1", "f430"), ("f428", "1"), ("f431", "f432"), ("f433", "1"), ("1", "1"), ("f435", "1"), ("1", "f436"), ("1", "a22"), ("f438", "1"), ("1", "f439"), ("1", "b23"), ("f441", "1"), ("1", "f442"), ("1", "f437"), ("f444", "1"), ("1", "f445"), ("f446", "b23"), ("1", "f440"), ("f448", "1"), ("1", "f449"), ("f447", "1"), ("f450", "f451"), ("f452", "1"), ("1", "1"), ("f454", "1"), ("1", "f455"), ("1", "a23"), ("f457", "1"), ("1", "f458"), ("1", "b33"), ("f460", "1"), ("1", "f461"), ("1", "f456"), ("f463", "1"), ("1", "f464"), ("f465", "b33"), ("1", "f459"), ("f467", "1"), ("1", "f468"), ("f466", "1"), ("f469", "f470"), ("f471", "1"), ("1", "1"), ("f473", "1"), ("1", "f474"), ("1", "f475"), ("f476", "1"), ("1", "f477"), ("f453", "1"), ("f478", "f479"), ("1", "f434"), ("f481", "1"), ("1", "f482"), ("f480", "1"), ("f483", "f484"), ("1", "1"), ("f486", "1"), ("1", "f487"), ("1", "f488"), ("f489", "1"), ("1", "f490"), ("f472", "1"), ("f491", "f492"), ("1", "f485"), ("f494", "1"), ("1", "f495"), ("f493", "1"), ("f496", "f497"), ("1", "1"), ("f499", "1"), ("1", "f500"), ("1", "a31"), ("f502", "1"), ("1", "f503"), ("1", "b11"), ("f505", "1"), ("1", "f506"), ("1", "f501"), ("f508", "1"), ("1", "f509"), ("f510", "b11"), ("1", "f504"), ("f512", "1"), ("1", "f513"), ("f511", "1"), ("f514", "f515"), ("f516", "1"), ("1", "1"), ("f518", "1"), ("1", "f519"), ("1", "a32"), ("f521", "1"), ("1", "f522"), ("1", "b21"), ("f524", "1"), ("1", "f525"), ("1", "f520"), ("f527", "1"), ("1", "f528"), ("f529", "b21"), ("1", "f523"), ("f531", "1"), ("1", "f532"), ("f530", "1"), ("f533", "f534"), ("f535", "1"), ("1", "1"), ("f537", "1"), ("1", "f538"), ("1", "a33"), ("f540", "1"), ("1", "f541"), ("1", "b31"), ("f543", "1"), ("1", "f544"), ("1", "f539"), ("f546", "1"), ("1", "f547"), ("f548", "b31"), ("1", "f542"), ("f550", "1"), ("1", "f551"), ("f549", "1"), ("f552", "f553"), ("f554", "1"), ("1", "1"), ("f556", "1"), ("1", "f557"), ("1", "f558"), ("f559", "1"), ("1", "f560"), ("f536", "1"), ("f561", "f562"), ("1", "f517"), ("f564", "1"), ("1", "f565"), ("f563", "1"), ("f566", "f567"), ("1", "1"), ("f569", "1"), ("1", "f570"), ("1", "f571"), ("f572", "1"), ("1", "f573"), ("f555", "1"), ("f574", "f575"), ("1", "f568"), ("f577", "1"), ("1", "f578"), ("f576", "1"), ("f579", "f580"), ("1", "1"), ("f582", "1"), ("1", "f583"), ("1", "a31"), ("f585", "1"), ("1", "f586"), ("1", "b12"), ("f588", "1"), ("1", "f589"), ("1", "f584"), ("f591", "1"), ("1", "f592"), ("f593", "b12"), ("1", "f587"), ("f595", "1"), ("1", "f596"), ("f594", "1"), ("f597", "f598"), ("f599", "1"), ("1", "1"), ("f601", "1"), ("1", "f602"), ("1", "a32"), ("f604", "1"), ("1", "f605"), ("1", "b22"), ("f607", "1"), ("1", "f608"), ("1", "f603"), ("f610", "1"), ("1", "f611"), ("f612", "b22"), ("1", "f606"), ("f614", "1"), ("1", "f615"), ("f613", "1"), ("f616", "f617"), ("f618", "1"), ("1", "1"), ("f620", "1"), ("1", "f621"), ("1", "a33"), ("f623", "1"), ("1", "f624"), ("1", "b32"), ("f626", "1"), ("1", "f627"), ("1", "f622"), ("f629", "1"), ("1", "f630"), ("f631", "b32"), ("1", "f625"), ("f633", "1"), ("1", "f634"), ("f632", "1"), ("f635", "f636"), ("f637", "1"), ("1", "1"), ("f639", "1"), ("1", "f640"), ("1", "f641"), ("f642", "1"), ("1", "f643"), ("f619", "1"), ("f644", "f645"), ("1", "f600"), ("f647", "1"), ("1", "f648"), ("f646", "1"), ("f649", "f650"), ("1", "1"), ("f652", "1"), ("1", "f653"), ("1", "f654"), ("f655", "1"), ("1", "f656"), ("f638", "1"), ("f657", "f658"), ("1", "f651"), ("f660", "1"), ("1", "f661"), ("f659", "1"), ("f662", "f663")],
        },
        ParametricChain {
            variables: &["a11", "a12", "a13", "a21", "a22", "a23", "a31", "a32", "a33", "b11", "b12", "b13", "b21", "b22", "b23", "b31", "b32", "b33"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a11"), ("f4", "1"), ("1", "f5"), ("1", "b11"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "b11"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "a12"), ("f23", "1"), ("1", "f24"), ("1", "b21"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b21"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "a13"), ("f42", "1"), ("1", "f43"), ("1", "b31"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "b31"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f60"), ("f61", "1"), ("1", "f62"), ("f38", "1"), ("f63", "f64"), ("1", "f19"), ("f66", "1"), ("1", "f67"), ("f65", "1"), ("f68", "f69"), ("1", "1"), ("f71", "1"), ("1", "f72"), ("1", "f73"), ("f74", "1"), ("1", "f75"), ("f57", "1"), ("f76", "f77"), ("1", "f70"), ("f79", "1"), ("1", "f80"), ("f78", "1"), ("f81", "f82"), ("1", "1"), ("f84", "1"), ("1", "f85"), ("1", "a11"), ("f87", "1"), ("1", "f88"), ("1", "b12"), ("f90", "1"), ("1", "f91"), ("1", "f86"), ("f93", "1"), ("1", "f94"), ("f95", "b12"), ("1", "f89"), ("f97", "1"), ("1", "f98"), ("f96", "1"), ("f99", "f100"), ("f101", "1"), ("1", "1"), ("f103", "1"), ("1", "f104"), ("1", "a12"), ("f106", "1"), ("1", "f107"), ("1", "b22"), ("f109", "1"), ("1", "f110"), ("1", "f105"), ("f112", "1"), ("1", "f113"), ("f114", "b22"), ("1", "f108"), ("f116", "1"), ("1", "f117"), ("f115", "1"), ("f118", "f119"), ("f120", "1"), ("1", "1"), ("f122", "1"), ("1", "f123"), ("1", "a13"), ("f125", "1"), ("1", "f126"), ("1", "b32"), ("f128", "1"), ("1", "f129"), ("1", "f124"), ("f131", "1"), ("1", "f132"), ("f133", "b32"), ("1", "f127"), ("f135", "1"), ("1", "f136"), ("f134", "1"), ("f137", "f138"), ("f139", "1"), ("1", "1"), ("f141", "1"), ("1", "f142"), ("1", "f143"), ("f144", "1"), ("1", "f145"), ("f121", "1"), ("f146", "f147"), ("1", "f102"), ("f149", "1"), ("1", "f150"), ("f148", "1"), ("f151", "f152"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "f156"), ("f157", "1"), ("1", "f158"), ("f140", "1"), ("f159", "f160"), ("1", "f153"), ("f162", "1"), ("1", "f163"), ("f161", "1"), ("f164", "f165"), ("1", "1"), ("f167", "1"), ("1", "f168"), ("1", "a11"), ("f170", "1"), ("1", "f171"), ("1", "b13"), ("f173", "1"), ("1", "f174"), ("1", "f169"), ("f176", "1"), ("1", "f177"), ("f178", "b13"), ("1", "f172"), ("f180", "1"), ("1", "f181"), ("f179", "1"), ("f182", "f183"), ("f184", "1"), ("1", "1"), ("f186", "1"), ("1", "f187"), ("1", "a12"), ("f189", "1"), ("1", "f190"), ("1", "b23"), ("f192", "1"), ("1", "f193"), ("1", "f188"), ("f195", "1"), ("1", "f196"), ("f197", "b23"), ("1", "f191"), ("f199", "1"), ("1", "f200"), ("f198", "1"), ("f201", "f202"), ("f203", "1"), ("1", "1"), ("f205", "1"), ("1", "f206"), ("1", "a13"), ("f208", "1"), ("1", "f209"), ("1", "b33"), ("f211", "1"), ("1", "f212"), ("1", "f207"), ("f214", "1"), ("1", "f215"), ("f216", "b33"), ("1", "f210"), ("f218", "1"), ("1", "f219"), ("f217", "1"), ("f220", "f221"), ("f222", "1"), ("1", "1"), ("f224", "1"), ("1", "f225"), ("1", "f226"), ("f227", "1"), ("1", "f228"), ("f204", "1"), ("f229", "f230"), ("1", "f185"), ("f232", "1"), ("1", "f233"), ("f231", "1"), ("f234", "f235"), ("1", "1"), ("f237", "1"), ("1", "f238"), ("1", "f239"), ("f240", "1"), ("1", "f241"), ("f223", "1"), ("f242", "f243"), ("1", "f236"), ("f245", "1"), ("1", "f246"), ("f244", "1"), ("f247", "f248"), ("1", "1"), ("f250", "1"), ("1", "f251"), ("1", "a21"), ("f253", "1"), ("1", "f254"), ("1", "b11"), ("f256", "1"), ("1", "f257"), ("1", "f252"), ("f259", "1"), ("1", "f260"), ("f261", "b11"), ("1", "f255"), ("f263", "1"), ("1", "f264"), ("f262", "1"), ("f265", "f266"), ("f267", "1"), ("1", "1"), ("f269", "1"), ("1", "f270"), ("1", "a22"), ("f272", "1"), ("1", "f273"), ("1", "b21"), ("f275", "1"), ("1", "f276"), ("1", "f271"), ("f278", "1"), ("1", "f279"), ("f280", "b21"), ("1", "f274"), ("f282", "1"), ("1", "f283"), ("f281", "1"), ("f284", "f285"), ("f286", "1"), ("1", "1"), ("f288", "1"), ("1", "f289"), ("1", "a23"), ("f291", "1"), ("1", "f292"), ("1", "b31"), ("f294", "1"), ("1", "f295"), ("1", "f290"), ("f297", "1"), ("1", "f298"), ("f299", "b31"), ("1", "f293"), ("f301", "1"), ("1", "f302"), ("f300", "1"), ("f303", "f304"), ("f305", "1"), ("1", "1"), ("f307", "1"), ("1", "f308"), ("1", "f309"), ("f310", "1"), ("1", "f311"), ("f287", "1"), ("f312", "f313"), ("1", "f268"), ("f315", "1"), ("1", "f316"), ("f314", "1"), ("f317", "f318"), ("1", "1"), ("f320", "1"), ("1", "f321"), ("1", "f322"), ("f323", "1"), ("1", "f324"), ("f306", "1"), ("f325", "f326"), ("1", "f319"), ("f328", "1"), ("1", "f329"), ("f327", "1"), ("f330", "f331"), ("1", "1"), ("f333", "1"), ("1", "f334"), ("1", "a21"), ("f336", "1"), ("1", "f337"), ("1", "b12"), ("f339", "1"), ("1", "f340"), ("1", "f335"), ("f342", "1"), ("1", "f343"), ("f344", "b12"), ("1", "f338"), ("f346", "1"), ("1", "f347"), ("f345", "1"), ("f348", "f349"), ("f350", "1"), ("1", "1"), ("f352", "1"), ("1", "f353"), ("1", "a22"), ("f355", "1"), ("1", "f356"), ("1", "b22"), ("f358", "1"), ("1", "f359"), ("1", "f354"), ("f361", "1"), ("1", "f362"), ("f363", "b22"), ("1", "f357"), ("f365", "1"), ("1", "f366"), ("f364", "1"), ("f367", "f368"), ("f369", "1"), ("1", "1"), ("f371", "1"), ("1", "f372"), ("1", "a23"), ("f374", "1"), ("1", "f375"), ("1", "b32"), ("f377", "1"), ("1", "f378"), ("1", "f373"), ("f380", "1"), ("1", "f381"), ("f382", "b32"), ("1", "f376"), ("f384", "1"), ("1", "f385"), ("f383", "1"), ("f386", "f387"), ("f388", "1"), ("1", "1"), ("f390", "1"), ("1", "f391"), ("1", "f392"), ("f393", "1"), ("1", "f394"), ("f370", "1"), ("f395", "f396"), ("1", "f351"), ("f398", "1"), ("1", "f399"), ("f397", "1"), ("f400", "f401"), ("1", "1"), ("f403", "1"), ("1", "f404"), ("1", "f405"), ("f406", "1"), ("1", "f407"), ("f389", "1"), ("f408", "f409"), ("1", "f402"), ("f411", "1"), ("1", "f412"), ("f410", "1"), ("f413", "f414"), ("1", "1"), ("f416", "1"), ("1", "f417"), ("1", "a21"), ("f419", "1"), ("1", "f420"), ("1", "b13"), ("f422", "1"), ("1", "f423"), ("1", "f418"), ("f425", "1"), ("1", "f426"), ("f427", "b13"), ("1", "f421"), ("f429", "1"), ("1", "f430"), ("f428", "1"), ("f431", "f432"), ("f433", "1"), ("1", "1"), ("f435", "1"), ("1", "f436"), ("1", "a22"), ("f438", "1"), ("1", "f439"), ("1", "b23"), ("f441", "1"), ("1", "f442"), ("1", "f437"), ("f444", "1"), ("1", "f445"), ("f446", "b23"), ("1", "f440"), ("f448", "1"), ("1", "f449"), ("f447", "1"), ("f450", "f451"), ("f452", "1"), ("1", "1"), ("f454", "1"), ("1", "f455"), ("1", "a23"), ("f457", "1"), ("1", "f458"), ("1", "b33"), ("f460", "1"), ("1", "f461"), ("1", "f456"), ("f463", "1"), ("1", "f464"), ("f465", "b33"), ("1", "f459"), ("f467", "1"), ("1", "f468"), ("f466", "1"), ("f469", "f470"), ("f471", "1"), ("1", "1"), ("f473", "1"), ("1", "f474"), ("1", "f475"), ("f476", "1"), ("1", "f477"), ("f453", "1"), ("f478", "f479"), ("1", "f434"), ("f481", "1"), ("1", "f482"), ("f480", "1"), ("f483", "f484"), ("1", "1"), ("f486", "1"), ("1", "f487"), ("1", "f488"), ("f489", "1"), ("1", "f490"), ("f472", "1"), ("f491", "f492"), ("1", "f485"), ("f494", "1"), ("1", "f495"), ("f493", "1"), ("f496", "f497"), ("1", "1"), ("f499", "1"), ("1", "f500"), ("1", "a31"), ("f502", "1"), ("1", "f503"), ("1", "b11"), ("f505", "1"), ("1", "f506"), ("1", "f501"), ("f508", "1"), ("1", "f509"), ("f510", "b11"), ("1", "f504"), ("f512", "1"), ("1", "f513"), ("f511", "1"), ("f514", "f515"), ("f516", "1"), ("1", "1"), ("f518", "1"), ("1", "f519"), ("1", "a32"), ("f521", "1"), ("1", "f522"), ("1", "b21"), ("f524", "1"), ("1", "f525"), ("1", "f520"), ("f527", "1"), ("1", "f528"), ("f529", "b21"), ("1", "f523"), ("f531", "1"), ("1", "f532"), ("f530", "1"), ("f533", "f534"), ("f535", "1"), ("1", "1"), ("f537", "1"), ("1", "f538"), ("1", "a33"), ("f540", "1"), ("1", "f541"), ("1", "b31"), ("f543", "1"), ("1", "f544"), ("1", "f539"), ("f546", "1"), ("1", "f547"), ("f548", "b31"), ("1", "f542"), ("f550", "1"), ("1", "f551"), ("f549", "1"), ("f552", "f553"), ("f554", "1"), ("1", "1"), ("f556", "1"), ("1", "f557"), ("1", "f558"), ("f559", "1"), ("1", "f560"), ("f536", "1"), ("f561", "f562"), ("1", "f517"), ("f564", "1"), ("1", "f565"), ("f563", "1"), ("f566", "f567"), ("1", "1"), ("f569", "1"), ("1", "f570"), ("1", "f571"), ("f572", "1"), ("1", "f573"), ("f555", "1"), ("f574", "f575"), ("1", "f568"), ("f577", "1"), ("1", "f578"), ("f576", "1"), ("f579", "f580"), ("1", "1"), ("f582", "1"), ("1", "f583"), ("1", "a31"), ("f585", "1"), ("1", "f586"), ("1", "b12"), ("f588", "1"), ("1", "f589"), ("1", "f584"), ("f591", "1"), ("1", "f592"), ("f593", "b12"), ("1", "f587"), ("f595", "1"), ("1", "f596"), ("f594", "1"), ("f597", "f598"), ("f599", "1"), ("1", "1"), ("f601", "1"), ("1", "f602"), ("1", "a32"), ("f604", "1"), ("1", "f605"), ("1", "b22"), ("f607", "1"), ("1", "f608"), ("1", "f603"), ("f610", "1"), ("1", "f611"), ("f612", "b22"), ("1", "f606"), ("f614", "1"), ("1", "f615"), ("f613", "1"), ("f616", "f617"), ("f618", "1"), ("1", "1"), ("f620", "1"), ("1", "f621"), ("1", "a33"), ("f623", "1"), ("1", "f624"), ("1", "b32"), ("f626", "1"), ("1", "f627"), ("1", "f622"), ("f629", "1"), ("1", "f630"), ("f631", "b32"), ("1", "f625"), ("f633", "1"), ("1", "f634"), ("f632", "1"), ("f635", "f636"), ("f637", "1"), ("1", "1"), ("f639", "1"), ("1", "f640"), ("1", "f641"), ("f642", "1"), ("1", "f643"), ("f619", "1"), ("f644", "f645"), ("1", "f600"), ("f647", "1"), ("1", "f648"), ("f646", "1"), ("f649", "f650"), ("1", "1"), ("f652", "1"), ("1", "f653"), ("1", "f654"), ("f655", "1"), ("1", "f656"), ("f638", "1"), ("f657", "f658"), ("1", "f651"), ("f660", "1"), ("1", "f661"), ("f659", "1"), ("f662", "f663"), ("1", "1"), ("f665", "1"), ("1", "f666"), ("1", "a31"), ("f668", "1"), ("1", "f669"), ("1", "b13"), ("f671", "1"), ("1", "f672"), ("1", "f667"), ("f674", "1"), ("1", "f675"), ("f676", "b13"), ("1", "f670"), ("f678", "1"), ("1", "f679"), ("f677", "1"), ("f680", "f681"), ("f682", "1"), ("1", "1"), ("f684", "1"), ("1", "f685"), ("1", "a32"), ("f687", "1"), ("1", "f688"), ("1", "b23"), ("f690", "1"), ("1", "f691"), ("1", "f686"), ("f693", "1"), ("1", "f694"), ("f695", "b23"), ("1", "f689"), ("f697", "1"), ("1", "f698"), ("f696", "1"), ("f699", "f700"), ("f701", "1"), ("1", "1"), ("f703", "1"), ("1", "f704"), ("1", "a33"), ("f706", "1"), ("1", "f707"), ("1", "b33"), ("f709", "1"), ("1", "f710"), ("1", "f705"), ("f712", "1"), ("1", "f713"), ("f714", "b33"), ("1", "f708"), ("f716", "1"), ("1", "f717"), ("f715", "1"), ("f718", "f719"), ("f720", "1"), ("1", "1"), ("f722", "1"), ("1", "f723"), ("1", "f724"), ("f725", "1"), ("1", "f726"), ("f702", "1"), ("f727", "f728"), ("1", "f683"), ("f730", "1"), ("1", "f731"), ("f729", "1"), ("f732", "f733"), ("1", "1"), ("f735", "1"), ("1", "f736"), ("1", "f737"), ("f738", "1"), ("1", "f739"), ("f721", "1"), ("f740", "f741"), ("1", "f734"), ("f743", "1"), ("1", "f744"), ("f742", "1"), ("f745", "f746")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "3x3 matrix multiplication (9 components)",
    },
    MacroDefinition {
        shorthand_id: "MMP",
        function_class: FunctionClass::LinAlg,
        variant_tag: VariantTag::MultiOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a1", "b1", "c1", "d1", "a2", "b2", "c2", "d2"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a1"), ("f4", "1"), ("1", "f5"), ("1", "a2"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "a2"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b1"), ("f23", "1"), ("1", "f24"), ("1", "c2"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "c2"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f41"), ("f42", "1"), ("1", "f43"), ("f38", "1"), ("f44", "f45"), ("1", "f19"), ("f47", "1"), ("1", "f48"), ("f46", "1"), ("f49", "f50")],
        },
        ParametricChain {
            variables: &["a1", "b1", "c1", "d1", "a2", "b2", "c2", "d2"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a1"), ("f4", "1"), ("1", "f5"), ("1", "a2"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "a2"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b1"), ("f23", "1"), ("1", "f24"), ("1", "c2"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "c2"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f41"), ("f42", "1"), ("1", "f43"), ("f38", "1"), ("f44", "f45"), ("1", "f19"), ("f47", "1"), ("1", "f48"), ("f46", "1"), ("f49", "f50"), ("1", "1"), ("f52", "1"), ("1", "f53"), ("1", "a1"), ("f55", "1"), ("1", "f56"), ("1", "b2"), ("f58", "1"), ("1", "f59"), ("1", "f54"), ("f61", "1"), ("1", "f62"), ("f63", "b2"), ("1", "f57"), ("f65", "1"), ("1", "f66"), ("f64", "1"), ("f67", "f68"), ("f69", "1"), ("1", "1"), ("f71", "1"), ("1", "f72"), ("1", "b1"), ("f74", "1"), ("1", "f75"), ("1", "d2"), ("f77", "1"), ("1", "f78"), ("1", "f73"), ("f80", "1"), ("1", "f81"), ("f82", "d2"), ("1", "f76"), ("f84", "1"), ("1", "f85"), ("f83", "1"), ("f86", "f87"), ("f88", "1"), ("1", "1"), ("f90", "1"), ("1", "f91"), ("1", "f92"), ("f93", "1"), ("1", "f94"), ("f89", "1"), ("f95", "f96"), ("1", "f70"), ("f98", "1"), ("1", "f99"), ("f97", "1"), ("f100", "f101")],
        },
        ParametricChain {
            variables: &["a1", "b1", "c1", "d1", "a2", "b2", "c2", "d2"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a1"), ("f4", "1"), ("1", "f5"), ("1", "a2"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "a2"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b1"), ("f23", "1"), ("1", "f24"), ("1", "c2"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "c2"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f41"), ("f42", "1"), ("1", "f43"), ("f38", "1"), ("f44", "f45"), ("1", "f19"), ("f47", "1"), ("1", "f48"), ("f46", "1"), ("f49", "f50"), ("1", "1"), ("f52", "1"), ("1", "f53"), ("1", "a1"), ("f55", "1"), ("1", "f56"), ("1", "b2"), ("f58", "1"), ("1", "f59"), ("1", "f54"), ("f61", "1"), ("1", "f62"), ("f63", "b2"), ("1", "f57"), ("f65", "1"), ("1", "f66"), ("f64", "1"), ("f67", "f68"), ("f69", "1"), ("1", "1"), ("f71", "1"), ("1", "f72"), ("1", "b1"), ("f74", "1"), ("1", "f75"), ("1", "d2"), ("f77", "1"), ("1", "f78"), ("1", "f73"), ("f80", "1"), ("1", "f81"), ("f82", "d2"), ("1", "f76"), ("f84", "1"), ("1", "f85"), ("f83", "1"), ("f86", "f87"), ("f88", "1"), ("1", "1"), ("f90", "1"), ("1", "f91"), ("1", "f92"), ("f93", "1"), ("1", "f94"), ("f89", "1"), ("f95", "f96"), ("1", "f70"), ("f98", "1"), ("1", "f99"), ("f97", "1"), ("f100", "f101"), ("1", "1"), ("f103", "1"), ("1", "f104"), ("1", "c1"), ("f106", "1"), ("1", "f107"), ("1", "a2"), ("f109", "1"), ("1", "f110"), ("1", "f105"), ("f112", "1"), ("1", "f113"), ("f114", "a2"), ("1", "f108"), ("f116", "1"), ("1", "f117"), ("f115", "1"), ("f118", "f119"), ("f120", "1"), ("1", "1"), ("f122", "1"), ("1", "f123"), ("1", "d1"), ("f125", "1"), ("1", "f126"), ("1", "c2"), ("f128", "1"), ("1", "f129"), ("1", "f124"), ("f131", "1"), ("1", "f132"), ("f133", "c2"), ("1", "f127"), ("f135", "1"), ("1", "f136"), ("f134", "1"), ("f137", "f138"), ("f139", "1"), ("1", "1"), ("f141", "1"), ("1", "f142"), ("1", "f143"), ("f144", "1"), ("1", "f145"), ("f140", "1"), ("f146", "f147"), ("1", "f121"), ("f149", "1"), ("1", "f150"), ("f148", "1"), ("f151", "f152")],
        },
        ParametricChain {
            variables: &["a1", "b1", "c1", "d1", "a2", "b2", "c2", "d2"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a1"), ("f4", "1"), ("1", "f5"), ("1", "a2"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "a2"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b1"), ("f23", "1"), ("1", "f24"), ("1", "c2"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "c2"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f41"), ("f42", "1"), ("1", "f43"), ("f38", "1"), ("f44", "f45"), ("1", "f19"), ("f47", "1"), ("1", "f48"), ("f46", "1"), ("f49", "f50"), ("1", "1"), ("f52", "1"), ("1", "f53"), ("1", "a1"), ("f55", "1"), ("1", "f56"), ("1", "b2"), ("f58", "1"), ("1", "f59"), ("1", "f54"), ("f61", "1"), ("1", "f62"), ("f63", "b2"), ("1", "f57"), ("f65", "1"), ("1", "f66"), ("f64", "1"), ("f67", "f68"), ("f69", "1"), ("1", "1"), ("f71", "1"), ("1", "f72"), ("1", "b1"), ("f74", "1"), ("1", "f75"), ("1", "d2"), ("f77", "1"), ("1", "f78"), ("1", "f73"), ("f80", "1"), ("1", "f81"), ("f82", "d2"), ("1", "f76"), ("f84", "1"), ("1", "f85"), ("f83", "1"), ("f86", "f87"), ("f88", "1"), ("1", "1"), ("f90", "1"), ("1", "f91"), ("1", "f92"), ("f93", "1"), ("1", "f94"), ("f89", "1"), ("f95", "f96"), ("1", "f70"), ("f98", "1"), ("1", "f99"), ("f97", "1"), ("f100", "f101"), ("1", "1"), ("f103", "1"), ("1", "f104"), ("1", "c1"), ("f106", "1"), ("1", "f107"), ("1", "a2"), ("f109", "1"), ("1", "f110"), ("1", "f105"), ("f112", "1"), ("1", "f113"), ("f114", "a2"), ("1", "f108"), ("f116", "1"), ("1", "f117"), ("f115", "1"), ("f118", "f119"), ("f120", "1"), ("1", "1"), ("f122", "1"), ("1", "f123"), ("1", "d1"), ("f125", "1"), ("1", "f126"), ("1", "c2"), ("f128", "1"), ("1", "f129"), ("1", "f124"), ("f131", "1"), ("1", "f132"), ("f133", "c2"), ("1", "f127"), ("f135", "1"), ("1", "f136"), ("f134", "1"), ("f137", "f138"), ("f139", "1"), ("1", "1"), ("f141", "1"), ("1", "f142"), ("1", "f143"), ("f144", "1"), ("1", "f145"), ("f140", "1"), ("f146", "f147"), ("1", "f121"), ("f149", "1"), ("1", "f150"), ("f148", "1"), ("f151", "f152"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "c1"), ("f157", "1"), ("1", "f158"), ("1", "b2"), ("f160", "1"), ("1", "f161"), ("1", "f156"), ("f163", "1"), ("1", "f164"), ("f165", "b2"), ("1", "f159"), ("f167", "1"), ("1", "f168"), ("f166", "1"), ("f169", "f170"), ("f171", "1"), ("1", "1"), ("f173", "1"), ("1", "f174"), ("1", "d1"), ("f176", "1"), ("1", "f177"), ("1", "d2"), ("f179", "1"), ("1", "f180"), ("1", "f175"), ("f182", "1"), ("1", "f183"), ("f184", "d2"), ("1", "f178"), ("f186", "1"), ("1", "f187"), ("f185", "1"), ("f188", "f189"), ("f190", "1"), ("1", "1"), ("f192", "1"), ("1", "f193"), ("1", "f194"), ("f195", "1"), ("1", "f196"), ("f191", "1"), ("f197", "f198"), ("1", "f172"), ("f200", "1"), ("1", "f201"), ("f199", "1"), ("f202", "f203")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "2x2 matrix multiplication",
    },
    MacroDefinition {
        shorthand_id: "MSH",
        function_class: FunctionClass::NnActivation,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("x", "1"), ("1", "1"), ("f2", "1"), ("1", "f3"), ("1", "f4"), ("f5", "1"), ("1", "f6"), ("f1", "1"), ("f7", "f8"), ("1", "1"), ("f10", "1"), ("1", "f11"), ("f9", "1"), ("f12", "f13"), ("1", "f14"), ("f15", "1"), ("1", "f16"), ("f17", "1"), ("1", "1"), ("f19", "1"), ("1", "f20"), ("1", "f21"), ("f22", "1"), ("1", "f23"), ("f17", "1"), ("f24", "f25"), ("f26", "1"), ("1", "f18"), ("f28", "1"), ("1", "f29"), ("f27", "1"), ("f30", "f31"), ("1", "1"), ("f33", "1"), ("1", "f34"), ("1", "f35"), ("f36", "1"), ("1", "f37"), ("f27", "1"), ("f38", "f39"), ("1", "f18"), ("f41", "1"), ("1", "f42"), ("f40", "1"), ("f43", "f44"), ("1", "f32"), ("f46", "1"), ("1", "f47"), ("1", "f48"), ("f49", "1"), ("1", "f50"), ("f51", "f45"), ("f52", "1"), ("1", "1"), ("f54", "1"), ("1", "f55"), ("1", "x"), ("f57", "1"), ("1", "f58"), ("1", "f53"), ("f60", "1"), ("1", "f61"), ("1", "f56"), ("f63", "1"), ("1", "f64"), ("f65", "f53"), ("1", "f59"), ("f67", "1"), ("1", "f68"), ("f66", "1"), ("f69", "f70"), ("f71", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Mish = x * tanh(softplus(x))",
    },
    MacroDefinition {
        shorthand_id: "MUL",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "y"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "x"), ("f4", "1"), ("1", "f5"), ("1", "y"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "y"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "x * y",
    },
    MacroDefinition {
        shorthand_id: "MXB",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["v", "m", "kT", "prefactor"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "v"), ("f4", "1"), ("1", "f5"), ("1", "v"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "v"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "1"), ("f23", "1"), ("1", "f24"), ("1", "kT"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "kT"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "m"), ("f42", "1"), ("1", "f43"), ("1", "f19"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "f19"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "f57"), ("f58", "1"), ("1", "f59"), ("1", "f60"), ("f61", "1"), ("1", "f62"), ("f63", "f38"), ("f64", "1"), ("1", "1"), ("f66", "1"), ("1", "f67"), ("1", "f68"), ("f69", "1"), ("1", "f70"), ("f65", "1"), ("f71", "f72"), ("1", "1"), ("f74", "1"), ("1", "f75"), ("1", "prefactor"), ("f77", "1"), ("1", "f78"), ("1", "f19"), ("f80", "1"), ("1", "f81"), ("1", "f76"), ("f83", "1"), ("1", "f84"), ("f85", "f19"), ("1", "f79"), ("f87", "1"), ("1", "f88"), ("f86", "1"), ("f89", "f90"), ("f91", "1"), ("f73", "1"), ("1", "1"), ("f94", "1"), ("1", "f95"), ("1", "f92"), ("f97", "1"), ("1", "f98"), ("1", "f93"), ("f100", "1"), ("1", "f101"), ("1", "f96"), ("f103", "1"), ("1", "f104"), ("f105", "f93"), ("1", "f99"), ("f107", "1"), ("1", "f108"), ("f106", "1"), ("f109", "f110"), ("f111", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Maxwell-Boltzmann speed distribution",
    },
    MacroDefinition {
        shorthand_id: "MXY",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "y", "half"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("y", "1"), ("f6", "f7"), ("1", "x"), ("f9", "1"), ("1", "f10"), ("f8", "1"), ("f11", "f12"), ("1", "x"), ("f14", "1"), ("1", "f15"), ("y", "1"), ("f16", "f17"), ("1", "1"), ("f19", "1"), ("1", "f20"), ("1", "f13"), ("f22", "1"), ("1", "f23"), ("1", "half"), ("f25", "1"), ("1", "f26"), ("1", "f21"), ("f28", "1"), ("1", "f29"), ("f30", "half"), ("1", "f24"), ("f32", "1"), ("1", "f33"), ("f31", "1"), ("f34", "f35"), ("f36", "1"), ("1", "1"), ("f38", "1"), ("1", "f39"), ("1", "f18"), ("f41", "1"), ("1", "f42"), ("1", "f18"), ("f44", "1"), ("1", "f45"), ("1", "f40"), ("f47", "1"), ("1", "f48"), ("f49", "f18"), ("1", "f43"), ("f51", "1"), ("1", "f52"), ("f50", "1"), ("f53", "f54"), ("f55", "1"), ("1", "f56"), ("f57", "1"), ("1", "f58"), ("1", "1"), ("f60", "1"), ("1", "f61"), ("1", "half"), ("f63", "1"), ("1", "f64"), ("1", "f59"), ("f66", "1"), ("1", "f67"), ("1", "f62"), ("f69", "1"), ("1", "f70"), ("f71", "f59"), ("1", "f65"), ("f73", "1"), ("1", "f74"), ("f72", "1"), ("f75", "f76"), ("f77", "1"), ("f78", "1"), ("1", "1"), ("f80", "1"), ("1", "f81"), ("1", "f79"), ("f83", "1"), ("1", "f84"), ("1", "half"), ("f86", "1"), ("1", "f87"), ("1", "f82"), ("f89", "1"), ("1", "f90"), ("f91", "half"), ("1", "f85"), ("f93", "1"), ("1", "f94"), ("f92", "1"), ("f95", "f96"), ("f97", "1"), ("1", "1"), ("f99", "1"), ("1", "f100"), ("1", "f101"), ("f102", "1"), ("1", "f103"), ("f98", "1"), ("f104", "f105"), ("1", "f37"), ("f107", "1"), ("1", "f108"), ("f106", "1"), ("f109", "f110")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "max(x, y) via smooth-max",
    },
    MacroDefinition {
        shorthand_id: "NEG",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["y"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("y", "1"), ("f6", "f7")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "negation -y",
    },
    MacroDefinition {
        shorthand_id: "NEW",
        function_class: FunctionClass::NumericalMethod,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "f_of_x", "fprime_of_x"],
            levels: &[("1", "f_of_x"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("f6", "fprime_of_x"), ("f7", "1"), ("1", "x"), ("f9", "1"), ("1", "f10"), ("f8", "1"), ("f11", "f12")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Newton-Raphson step x - f(x)/f'(x)",
    },
    MacroDefinition {
        shorthand_id: "OML",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("f3", "x")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "1 - ln(x)",
    },
    MacroDefinition {
        shorthand_id: "ORV",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["G", "M", "r", "half"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "G"), ("f4", "1"), ("1", "f5"), ("1", "M"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "M"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "f19"), ("f20", "1"), ("1", "f21"), ("1", "f22"), ("f23", "1"), ("1", "f24"), ("f25", "r"), ("f26", "1"), ("1", "f27"), ("f28", "1"), ("1", "f29"), ("1", "1"), ("f31", "1"), ("1", "f32"), ("1", "half"), ("f34", "1"), ("1", "f35"), ("1", "f30"), ("f37", "1"), ("1", "f38"), ("1", "f33"), ("f40", "1"), ("1", "f41"), ("f42", "f30"), ("1", "f36"), ("f44", "1"), ("1", "f45"), ("f43", "1"), ("f46", "f47"), ("f48", "1"), ("f49", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "orbital velocity sqrt(GM/r)",
    },
    MacroDefinition {
        shorthand_id: "PLK",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["nu", "T", "prefactor", "hnu_kt"],
            levels: &[("hnu_kt", "1"), ("1", "f1"), ("f2", "1"), ("1", "f3"), ("1", "1"), ("f4", "f5"), ("1", "prefactor"), ("f7", "1"), ("1", "f8"), ("1", "f9"), ("f10", "1"), ("1", "f11"), ("f12", "f6"), ("f13", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Planck blackbody (sender provides hnu/kT)",
    },
    MacroDefinition {
        shorthand_id: "POW",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "y"],
            levels: &[("1", "x"), ("f1", "1"), ("1", "f2"), ("1", "1"), ("f4", "1"), ("1", "f5"), ("1", "y"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("1", "f6"), ("f13", "1"), ("1", "f14"), ("f15", "f3"), ("1", "f9"), ("f17", "1"), ("1", "f18"), ("f16", "1"), ("f19", "f20"), ("f21", "1"), ("f22", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "x^y = exp(y * ln(x))",
    },
    MacroDefinition {
        shorthand_id: "QML",
        function_class: FunctionClass::LinAlg,
        variant_tag: VariantTag::MultiOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a1", "b1", "c1", "d1", "a2", "b2", "c2", "d2"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a1"), ("f4", "1"), ("1", "f5"), ("1", "a2"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "a2"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b1"), ("f23", "1"), ("1", "f24"), ("1", "b2"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b2"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42"), ("1", "1"), ("f44", "1"), ("1", "f45"), ("1", "c1"), ("f47", "1"), ("1", "f48"), ("1", "c2"), ("f50", "1"), ("1", "f51"), ("1", "f46"), ("f53", "1"), ("1", "f54"), ("f55", "c2"), ("1", "f49"), ("f57", "1"), ("1", "f58"), ("f56", "1"), ("f59", "f60"), ("f61", "1"), ("1", "f43"), ("f63", "1"), ("1", "f64"), ("f62", "1"), ("f65", "f66"), ("1", "1"), ("f68", "1"), ("1", "f69"), ("1", "d1"), ("f71", "1"), ("1", "f72"), ("1", "d2"), ("f74", "1"), ("1", "f75"), ("1", "f70"), ("f77", "1"), ("1", "f78"), ("f79", "d2"), ("1", "f73"), ("f81", "1"), ("1", "f82"), ("f80", "1"), ("f83", "f84"), ("f85", "1"), ("1", "f67"), ("f87", "1"), ("1", "f88"), ("f86", "1"), ("f89", "f90"), ("1", "1"), ("f92", "1"), ("1", "f93"), ("1", "a1"), ("f95", "1"), ("1", "f96"), ("1", "b2"), ("f98", "1"), ("1", "f99"), ("1", "f94"), ("f101", "1"), ("1", "f102"), ("f103", "b2"), ("1", "f97"), ("f105", "1"), ("1", "f106"), ("f104", "1"), ("f107", "f108"), ("f109", "1"), ("1", "1"), ("f111", "1"), ("1", "f112"), ("1", "a2"), ("f114", "1"), ("1", "f115"), ("1", "b1"), ("f117", "1"), ("1", "f118"), ("1", "f113"), ("f120", "1"), ("1", "f121"), ("f122", "b1"), ("1", "f116"), ("f124", "1"), ("1", "f125"), ("f123", "1"), ("f126", "f127"), ("f128", "1"), ("1", "f110"), ("f130", "1"), ("1", "f131"), ("f129", "1"), ("f132", "f133"), ("1", "1"), ("f135", "1"), ("1", "f136"), ("1", "c1"), ("f138", "1"), ("1", "f139"), ("1", "d2"), ("f141", "1"), ("1", "f142"), ("1", "f137"), ("f144", "1"), ("1", "f145"), ("f146", "d2"), ("1", "f140"), ("f148", "1"), ("1", "f149"), ("f147", "1"), ("f150", "f151"), ("f152", "1"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "f156"), ("f157", "1"), ("1", "f158"), ("f153", "1"), ("f159", "f160"), ("1", "f134"), ("f162", "1"), ("1", "f163"), ("f161", "1"), ("f164", "f165"), ("1", "1"), ("f167", "1"), ("1", "f168"), ("1", "d1"), ("f170", "1"), ("1", "f171"), ("1", "c2"), ("f173", "1"), ("1", "f174"), ("1", "f169"), ("f176", "1"), ("1", "f177"), ("f178", "c2"), ("1", "f172"), ("f180", "1"), ("1", "f181"), ("f179", "1"), ("f182", "f183"), ("f184", "1"), ("1", "1"), ("f186", "1"), ("1", "f187"), ("1", "f188"), ("f189", "1"), ("1", "f190"), ("f185", "1"), ("f191", "f192"), ("1", "1"), ("f194", "1"), ("1", "f195"), ("1", "f196"), ("f197", "1"), ("1", "f198"), ("f193", "1"), ("f199", "f200"), ("1", "f166"), ("f202", "1"), ("1", "f203"), ("f201", "1"), ("f204", "f205"), ("1", "1"), ("f207", "1"), ("1", "f208"), ("1", "a1"), ("f210", "1"), ("1", "f211"), ("1", "c2"), ("f213", "1"), ("1", "f214"), ("1", "f209"), ("f216", "1"), ("1", "f217"), ("f218", "c2"), ("1", "f212"), ("f220", "1"), ("1", "f221"), ("f219", "1"), ("f222", "f223"), ("f224", "1"), ("1", "1"), ("f226", "1"), ("1", "f227"), ("1", "c1"), ("f229", "1"), ("1", "f230"), ("1", "a2"), ("f232", "1"), ("1", "f233"), ("1", "f228"), ("f235", "1"), ("1", "f236"), ("f237", "a2"), ("1", "f231"), ("f239", "1"), ("1", "f240"), ("f238", "1"), ("f241", "f242"), ("f243", "1"), ("1", "f225"), ("f245", "1"), ("1", "f246"), ("f244", "1"), ("f247", "f248"), ("1", "1"), ("f250", "1"), ("1", "f251"), ("1", "d1"), ("f253", "1"), ("1", "f254"), ("1", "b2"), ("f256", "1"), ("1", "f257"), ("1", "f252"), ("f259", "1"), ("1", "f260"), ("f261", "b2"), ("1", "f255"), ("f263", "1"), ("1", "f264"), ("f262", "1"), ("f265", "f266"), ("f267", "1"), ("1", "1"), ("f269", "1"), ("1", "f270"), ("1", "f271"), ("f272", "1"), ("1", "f273"), ("f268", "1"), ("f274", "f275"), ("1", "f249"), ("f277", "1"), ("1", "f278"), ("f276", "1"), ("f279", "f280"), ("1", "1"), ("f282", "1"), ("1", "f283"), ("1", "b1"), ("f285", "1"), ("1", "f286"), ("1", "d2"), ("f288", "1"), ("1", "f289"), ("1", "f284"), ("f291", "1"), ("1", "f292"), ("f293", "d2"), ("1", "f287"), ("f295", "1"), ("1", "f296"), ("f294", "1"), ("f297", "f298"), ("f299", "1"), ("1", "1"), ("f301", "1"), ("1", "f302"), ("1", "f303"), ("f304", "1"), ("1", "f305"), ("f300", "1"), ("f306", "f307"), ("1", "1"), ("f309", "1"), ("1", "f310"), ("1", "f311"), ("f312", "1"), ("1", "f313"), ("f308", "1"), ("f314", "f315"), ("1", "f281"), ("f317", "1"), ("1", "f318"), ("f316", "1"), ("f319", "f320"), ("1", "1"), ("f322", "1"), ("1", "f323"), ("1", "a1"), ("f325", "1"), ("1", "f326"), ("1", "d2"), ("f328", "1"), ("1", "f329"), ("1", "f324"), ("f331", "1"), ("1", "f332"), ("f333", "d2"), ("1", "f327"), ("f335", "1"), ("1", "f336"), ("f334", "1"), ("f337", "f338"), ("f339", "1"), ("1", "1"), ("f341", "1"), ("1", "f342"), ("1", "d1"), ("f344", "1"), ("1", "f345"), ("1", "a2"), ("f347", "1"), ("1", "f348"), ("1", "f343"), ("f350", "1"), ("1", "f351"), ("f352", "a2"), ("1", "f346"), ("f354", "1"), ("1", "f355"), ("f353", "1"), ("f356", "f357"), ("f358", "1"), ("1", "f340"), ("f360", "1"), ("1", "f361"), ("f359", "1"), ("f362", "f363"), ("1", "1"), ("f365", "1"), ("1", "f366"), ("1", "b1"), ("f368", "1"), ("1", "f369"), ("1", "c2"), ("f371", "1"), ("1", "f372"), ("1", "f367"), ("f374", "1"), ("1", "f375"), ("f376", "c2"), ("1", "f370"), ("f378", "1"), ("1", "f379"), ("f377", "1"), ("f380", "f381"), ("f382", "1"), ("1", "1"), ("f384", "1"), ("1", "f385"), ("1", "f386"), ("f387", "1"), ("1", "f388"), ("f383", "1"), ("f389", "f390"), ("1", "f364"), ("f392", "1"), ("1", "f393"), ("f391", "1"), ("f394", "f395"), ("1", "1"), ("f397", "1"), ("1", "f398"), ("1", "c1"), ("f400", "1"), ("1", "f401"), ("1", "b2"), ("f403", "1"), ("1", "f404"), ("1", "f399"), ("f406", "1"), ("1", "f407"), ("f408", "b2"), ("1", "f402"), ("f410", "1"), ("1", "f411"), ("f409", "1"), ("f412", "f413"), ("f414", "1"), ("1", "1"), ("f416", "1"), ("1", "f417"), ("1", "f418"), ("f419", "1"), ("1", "f420"), ("f415", "1"), ("f421", "f422"), ("1", "1"), ("f424", "1"), ("1", "f425"), ("1", "f426"), ("f427", "1"), ("1", "f428"), ("f423", "1"), ("f429", "f430"), ("1", "f396"), ("f432", "1"), ("1", "f433"), ("f431", "1"), ("f434", "f435"), ("1", "1"), ("f437", "1"), ("1", "f438"), ("1", "a1"), ("f440", "1"), ("1", "f441"), ("1", "a2"), ("f443", "1"), ("1", "f444"), ("1", "f439"), ("f446", "1"), ("1", "f447"), ("f448", "a2"), ("1", "f442"), ("f450", "1"), ("1", "f451"), ("f449", "1"), ("f452", "f453"), ("f454", "1"), ("1", "1"), ("f456", "1"), ("1", "f457"), ("1", "b1"), ("f459", "1"), ("1", "f460"), ("1", "b2"), ("f462", "1"), ("1", "f463"), ("1", "f458"), ("f465", "1"), ("1", "f466"), ("f467", "b2"), ("1", "f461"), ("f469", "1"), ("1", "f470"), ("f468", "1"), ("f471", "f472"), ("f473", "1"), ("1", "f455"), ("f475", "1"), ("1", "f476"), ("f474", "1"), ("f477", "f478"), ("1", "1"), ("f480", "1"), ("1", "f481"), ("1", "c1"), ("f483", "1"), ("1", "f484"), ("1", "c2"), ("f486", "1"), ("1", "f487"), ("1", "f482"), ("f489", "1"), ("1", "f490"), ("f491", "c2"), ("1", "f485"), ("f493", "1"), ("1", "f494"), ("f492", "1"), ("f495", "f496"), ("f497", "1"), ("1", "f479"), ("f499", "1"), ("1", "f500"), ("f498", "1"), ("f501", "f502"), ("1", "1"), ("f504", "1"), ("1", "f505"), ("1", "d1"), ("f507", "1"), ("1", "f508"), ("1", "d2"), ("f510", "1"), ("1", "f511"), ("1", "f506"), ("f513", "1"), ("1", "f514"), ("f515", "d2"), ("1", "f509"), ("f517", "1"), ("1", "f518"), ("f516", "1"), ("f519", "f520"), ("f521", "1"), ("1", "f503"), ("f523", "1"), ("1", "f524"), ("f522", "1"), ("f525", "f526"), ("1", "1"), ("f528", "1"), ("1", "f529"), ("1", "a1"), ("f531", "1"), ("1", "f532"), ("1", "b2"), ("f534", "1"), ("1", "f535"), ("1", "f530"), ("f537", "1"), ("1", "f538"), ("f539", "b2"), ("1", "f533"), ("f541", "1"), ("1", "f542"), ("f540", "1"), ("f543", "f544"), ("f545", "1"), ("1", "1"), ("f547", "1"), ("1", "f548"), ("1", "b1"), ("f550", "1"), ("1", "f551"), ("1", "a2"), ("f553", "1"), ("1", "f554"), ("1", "f549"), ("f556", "1"), ("1", "f557"), ("f558", "a2"), ("1", "f552"), ("f560", "1"), ("1", "f561"), ("f559", "1"), ("f562", "f563"), ("f564", "1"), ("1", "1"), ("f566", "1"), ("1", "f567"), ("1", "f568"), ("f569", "1"), ("1", "f570"), ("f565", "1"), ("f571", "f572"), ("1", "f546"), ("f574", "1"), ("1", "f575"), ("f573", "1"), ("f576", "f577"), ("1", "1"), ("f579", "1"), ("1", "f580"), ("1", "c1"), ("f582", "1"), ("1", "f583"), ("1", "d2"), ("f585", "1"), ("1", "f586"), ("1", "f581"), ("f588", "1"), ("1", "f589"), ("f590", "d2"), ("1", "f584"), ("f592", "1"), ("1", "f593"), ("f591", "1"), ("f594", "f595"), ("f596", "1"), ("1", "1"), ("f598", "1"), ("1", "f599"), ("1", "f600"), ("f601", "1"), ("1", "f602"), ("f597", "1"), ("f603", "f604"), ("1", "f578"), ("f606", "1"), ("1", "f607"), ("f605", "1"), ("f608", "f609"), ("1", "1"), ("f611", "1"), ("1", "f612"), ("1", "d1"), ("f614", "1"), ("1", "f615"), ("1", "c2"), ("f617", "1"), ("1", "f618"), ("1", "f613"), ("f620", "1"), ("1", "f621"), ("f622", "c2"), ("1", "f616"), ("f624", "1"), ("1", "f625"), ("f623", "1"), ("f626", "f627"), ("f628", "1"), ("1", "f610"), ("f630", "1"), ("1", "f631"), ("f629", "1"), ("f632", "f633"), ("1", "1"), ("f635", "1"), ("1", "f636"), ("1", "a1"), ("f638", "1"), ("1", "f639"), ("1", "c2"), ("f641", "1"), ("1", "f642"), ("1", "f637"), ("f644", "1"), ("1", "f645"), ("f646", "c2"), ("1", "f640"), ("f648", "1"), ("1", "f649"), ("f647", "1"), ("f650", "f651"), ("f652", "1"), ("1", "1"), ("f654", "1"), ("1", "f655"), ("1", "b1"), ("f657", "1"), ("1", "f658"), ("1", "d2"), ("f660", "1"), ("1", "f661"), ("1", "f656"), ("f663", "1"), ("1", "f664"), ("f665", "d2"), ("1", "f659"), ("f667", "1"), ("1", "f668"), ("f666", "1"), ("f669", "f670"), ("f671", "1"), ("1", "f653"), ("f673", "1"), ("1", "f674"), ("f672", "1"), ("f675", "f676"), ("1", "1"), ("f678", "1"), ("1", "f679"), ("1", "c1"), ("f681", "1"), ("1", "f682"), ("1", "a2"), ("f684", "1"), ("1", "f685"), ("1", "f680"), ("f687", "1"), ("1", "f688"), ("f689", "a2"), ("1", "f683"), ("f691", "1"), ("1", "f692"), ("f690", "1"), ("f693", "f694"), ("f695", "1"), ("1", "1"), ("f697", "1"), ("1", "f698"), ("1", "f699"), ("f700", "1"), ("1", "f701"), ("f696", "1"), ("f702", "f703"), ("1", "f677"), ("f705", "1"), ("1", "f706"), ("f704", "1"), ("f707", "f708"), ("1", "1"), ("f710", "1"), ("1", "f711"), ("1", "d1"), ("f713", "1"), ("1", "f714"), ("1", "b2"), ("f716", "1"), ("1", "f717"), ("1", "f712"), ("f719", "1"), ("1", "f720"), ("f721", "b2"), ("1", "f715"), ("f723", "1"), ("1", "f724"), ("f722", "1"), ("f725", "f726"), ("f727", "1"), ("1", "1"), ("f729", "1"), ("1", "f730"), ("1", "f731"), ("f732", "1"), ("1", "f733"), ("f728", "1"), ("f734", "f735"), ("1", "f709"), ("f737", "1"), ("1", "f738"), ("f736", "1"), ("f739", "f740"), ("1", "1"), ("f742", "1"), ("1", "f743"), ("1", "a1"), ("f745", "1"), ("1", "f746"), ("1", "a2"), ("f748", "1"), ("1", "f749"), ("1", "f744"), ("f751", "1"), ("1", "f752"), ("f753", "a2"), ("1", "f747"), ("f755", "1"), ("1", "f756"), ("f754", "1"), ("f757", "f758"), ("f759", "1"), ("1", "1"), ("f761", "1"), ("1", "f762"), ("1", "b1"), ("f764", "1"), ("1", "f765"), ("1", "b2"), ("f767", "1"), ("1", "f768"), ("1", "f763"), ("f770", "1"), ("1", "f771"), ("f772", "b2"), ("1", "f766"), ("f774", "1"), ("1", "f775"), ("f773", "1"), ("f776", "f777"), ("f778", "1"), ("1", "1"), ("f780", "1"), ("1", "f781"), ("1", "c1"), ("f783", "1"), ("1", "f784"), ("1", "c2"), ("f786", "1"), ("1", "f787"), ("1", "f782"), ("f789", "1"), ("1", "f790"), ("f791", "c2"), ("1", "f785"), ("f793", "1"), ("1", "f794"), ("f792", "1"), ("f795", "f796"), ("f797", "1"), ("1", "1"), ("f799", "1"), ("1", "f800"), ("1", "f801"), ("f802", "1"), ("1", "f803"), ("f798", "1"), ("f804", "f805"), ("1", "f779"), ("f807", "1"), ("1", "f808"), ("f806", "1"), ("f809", "f810"), ("1", "1"), ("f812", "1"), ("1", "f813"), ("1", "d1"), ("f815", "1"), ("1", "f816"), ("1", "d2"), ("f818", "1"), ("1", "f819"), ("1", "f814"), ("f821", "1"), ("1", "f822"), ("f823", "d2"), ("1", "f817"), ("f825", "1"), ("1", "f826"), ("f824", "1"), ("f827", "f828"), ("f829", "1"), ("1", "1"), ("f831", "1"), ("1", "f832"), ("1", "f833"), ("f834", "1"), ("1", "f835"), ("f830", "1"), ("f836", "f837"), ("1", "f811"), ("f839", "1"), ("1", "f840"), ("f838", "1"), ("f841", "f842"), ("1", "f760"), ("f844", "1"), ("1", "f845"), ("f843", "1"), ("f846", "f847")],
        },
        ParametricChain {
            variables: &["a1", "b1", "c1", "d1", "a2", "b2", "c2", "d2"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a1"), ("f4", "1"), ("1", "f5"), ("1", "a2"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "a2"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b1"), ("f23", "1"), ("1", "f24"), ("1", "b2"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b2"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42"), ("1", "1"), ("f44", "1"), ("1", "f45"), ("1", "c1"), ("f47", "1"), ("1", "f48"), ("1", "c2"), ("f50", "1"), ("1", "f51"), ("1", "f46"), ("f53", "1"), ("1", "f54"), ("f55", "c2"), ("1", "f49"), ("f57", "1"), ("1", "f58"), ("f56", "1"), ("f59", "f60"), ("f61", "1"), ("1", "f43"), ("f63", "1"), ("1", "f64"), ("f62", "1"), ("f65", "f66"), ("1", "1"), ("f68", "1"), ("1", "f69"), ("1", "d1"), ("f71", "1"), ("1", "f72"), ("1", "d2"), ("f74", "1"), ("1", "f75"), ("1", "f70"), ("f77", "1"), ("1", "f78"), ("f79", "d2"), ("1", "f73"), ("f81", "1"), ("1", "f82"), ("f80", "1"), ("f83", "f84"), ("f85", "1"), ("1", "f67"), ("f87", "1"), ("1", "f88"), ("f86", "1"), ("f89", "f90"), ("1", "1"), ("f92", "1"), ("1", "f93"), ("1", "a1"), ("f95", "1"), ("1", "f96"), ("1", "b2"), ("f98", "1"), ("1", "f99"), ("1", "f94"), ("f101", "1"), ("1", "f102"), ("f103", "b2"), ("1", "f97"), ("f105", "1"), ("1", "f106"), ("f104", "1"), ("f107", "f108"), ("f109", "1"), ("1", "1"), ("f111", "1"), ("1", "f112"), ("1", "a2"), ("f114", "1"), ("1", "f115"), ("1", "b1"), ("f117", "1"), ("1", "f118"), ("1", "f113"), ("f120", "1"), ("1", "f121"), ("f122", "b1"), ("1", "f116"), ("f124", "1"), ("1", "f125"), ("f123", "1"), ("f126", "f127"), ("f128", "1"), ("1", "f110"), ("f130", "1"), ("1", "f131"), ("f129", "1"), ("f132", "f133"), ("1", "1"), ("f135", "1"), ("1", "f136"), ("1", "c1"), ("f138", "1"), ("1", "f139"), ("1", "d2"), ("f141", "1"), ("1", "f142"), ("1", "f137"), ("f144", "1"), ("1", "f145"), ("f146", "d2"), ("1", "f140"), ("f148", "1"), ("1", "f149"), ("f147", "1"), ("f150", "f151"), ("f152", "1"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "f156"), ("f157", "1"), ("1", "f158"), ("f153", "1"), ("f159", "f160"), ("1", "f134"), ("f162", "1"), ("1", "f163"), ("f161", "1"), ("f164", "f165"), ("1", "1"), ("f167", "1"), ("1", "f168"), ("1", "d1"), ("f170", "1"), ("1", "f171"), ("1", "c2"), ("f173", "1"), ("1", "f174"), ("1", "f169"), ("f176", "1"), ("1", "f177"), ("f178", "c2"), ("1", "f172"), ("f180", "1"), ("1", "f181"), ("f179", "1"), ("f182", "f183"), ("f184", "1"), ("1", "1"), ("f186", "1"), ("1", "f187"), ("1", "f188"), ("f189", "1"), ("1", "f190"), ("f185", "1"), ("f191", "f192"), ("1", "1"), ("f194", "1"), ("1", "f195"), ("1", "f196"), ("f197", "1"), ("1", "f198"), ("f193", "1"), ("f199", "f200"), ("1", "f166"), ("f202", "1"), ("1", "f203"), ("f201", "1"), ("f204", "f205"), ("1", "1"), ("f207", "1"), ("1", "f208"), ("1", "a1"), ("f210", "1"), ("1", "f211"), ("1", "c2"), ("f213", "1"), ("1", "f214"), ("1", "f209"), ("f216", "1"), ("1", "f217"), ("f218", "c2"), ("1", "f212"), ("f220", "1"), ("1", "f221"), ("f219", "1"), ("f222", "f223"), ("f224", "1"), ("1", "1"), ("f226", "1"), ("1", "f227"), ("1", "c1"), ("f229", "1"), ("1", "f230"), ("1", "a2"), ("f232", "1"), ("1", "f233"), ("1", "f228"), ("f235", "1"), ("1", "f236"), ("f237", "a2"), ("1", "f231"), ("f239", "1"), ("1", "f240"), ("f238", "1"), ("f241", "f242"), ("f243", "1"), ("1", "f225"), ("f245", "1"), ("1", "f246"), ("f244", "1"), ("f247", "f248"), ("1", "1"), ("f250", "1"), ("1", "f251"), ("1", "d1"), ("f253", "1"), ("1", "f254"), ("1", "b2"), ("f256", "1"), ("1", "f257"), ("1", "f252"), ("f259", "1"), ("1", "f260"), ("f261", "b2"), ("1", "f255"), ("f263", "1"), ("1", "f264"), ("f262", "1"), ("f265", "f266"), ("f267", "1"), ("1", "1"), ("f269", "1"), ("1", "f270"), ("1", "f271"), ("f272", "1"), ("1", "f273"), ("f268", "1"), ("f274", "f275"), ("1", "f249"), ("f277", "1"), ("1", "f278"), ("f276", "1"), ("f279", "f280"), ("1", "1"), ("f282", "1"), ("1", "f283"), ("1", "b1"), ("f285", "1"), ("1", "f286"), ("1", "d2"), ("f288", "1"), ("1", "f289"), ("1", "f284"), ("f291", "1"), ("1", "f292"), ("f293", "d2"), ("1", "f287"), ("f295", "1"), ("1", "f296"), ("f294", "1"), ("f297", "f298"), ("f299", "1"), ("1", "1"), ("f301", "1"), ("1", "f302"), ("1", "f303"), ("f304", "1"), ("1", "f305"), ("f300", "1"), ("f306", "f307"), ("1", "1"), ("f309", "1"), ("1", "f310"), ("1", "f311"), ("f312", "1"), ("1", "f313"), ("f308", "1"), ("f314", "f315"), ("1", "f281"), ("f317", "1"), ("1", "f318"), ("f316", "1"), ("f319", "f320"), ("1", "1"), ("f322", "1"), ("1", "f323"), ("1", "a1"), ("f325", "1"), ("1", "f326"), ("1", "d2"), ("f328", "1"), ("1", "f329"), ("1", "f324"), ("f331", "1"), ("1", "f332"), ("f333", "d2"), ("1", "f327"), ("f335", "1"), ("1", "f336"), ("f334", "1"), ("f337", "f338"), ("f339", "1"), ("1", "1"), ("f341", "1"), ("1", "f342"), ("1", "d1"), ("f344", "1"), ("1", "f345"), ("1", "a2"), ("f347", "1"), ("1", "f348"), ("1", "f343"), ("f350", "1"), ("1", "f351"), ("f352", "a2"), ("1", "f346"), ("f354", "1"), ("1", "f355"), ("f353", "1"), ("f356", "f357"), ("f358", "1"), ("1", "f340"), ("f360", "1"), ("1", "f361"), ("f359", "1"), ("f362", "f363"), ("1", "1"), ("f365", "1"), ("1", "f366"), ("1", "b1"), ("f368", "1"), ("1", "f369"), ("1", "c2"), ("f371", "1"), ("1", "f372"), ("1", "f367"), ("f374", "1"), ("1", "f375"), ("f376", "c2"), ("1", "f370"), ("f378", "1"), ("1", "f379"), ("f377", "1"), ("f380", "f381"), ("f382", "1"), ("1", "1"), ("f384", "1"), ("1", "f385"), ("1", "f386"), ("f387", "1"), ("1", "f388"), ("f383", "1"), ("f389", "f390"), ("1", "f364"), ("f392", "1"), ("1", "f393"), ("f391", "1"), ("f394", "f395"), ("1", "1"), ("f397", "1"), ("1", "f398"), ("1", "c1"), ("f400", "1"), ("1", "f401"), ("1", "b2"), ("f403", "1"), ("1", "f404"), ("1", "f399"), ("f406", "1"), ("1", "f407"), ("f408", "b2"), ("1", "f402"), ("f410", "1"), ("1", "f411"), ("f409", "1"), ("f412", "f413"), ("f414", "1"), ("1", "1"), ("f416", "1"), ("1", "f417"), ("1", "f418"), ("f419", "1"), ("1", "f420"), ("f415", "1"), ("f421", "f422"), ("1", "1"), ("f424", "1"), ("1", "f425"), ("1", "f426"), ("f427", "1"), ("1", "f428"), ("f423", "1"), ("f429", "f430"), ("1", "f396"), ("f432", "1"), ("1", "f433"), ("f431", "1"), ("f434", "f435"), ("1", "1"), ("f437", "1"), ("1", "f438"), ("1", "a1"), ("f440", "1"), ("1", "f441"), ("1", "a2"), ("f443", "1"), ("1", "f444"), ("1", "f439"), ("f446", "1"), ("1", "f447"), ("f448", "a2"), ("1", "f442"), ("f450", "1"), ("1", "f451"), ("f449", "1"), ("f452", "f453"), ("f454", "1"), ("1", "1"), ("f456", "1"), ("1", "f457"), ("1", "b1"), ("f459", "1"), ("1", "f460"), ("1", "b2"), ("f462", "1"), ("1", "f463"), ("1", "f458"), ("f465", "1"), ("1", "f466"), ("f467", "b2"), ("1", "f461"), ("f469", "1"), ("1", "f470"), ("f468", "1"), ("f471", "f472"), ("f473", "1"), ("1", "f455"), ("f475", "1"), ("1", "f476"), ("f474", "1"), ("f477", "f478"), ("1", "1"), ("f480", "1"), ("1", "f481"), ("1", "c1"), ("f483", "1"), ("1", "f484"), ("1", "c2"), ("f486", "1"), ("1", "f487"), ("1", "f482"), ("f489", "1"), ("1", "f490"), ("f491", "c2"), ("1", "f485"), ("f493", "1"), ("1", "f494"), ("f492", "1"), ("f495", "f496"), ("f497", "1"), ("1", "f479"), ("f499", "1"), ("1", "f500"), ("f498", "1"), ("f501", "f502"), ("1", "1"), ("f504", "1"), ("1", "f505"), ("1", "d1"), ("f507", "1"), ("1", "f508"), ("1", "d2"), ("f510", "1"), ("1", "f511"), ("1", "f506"), ("f513", "1"), ("1", "f514"), ("f515", "d2"), ("1", "f509"), ("f517", "1"), ("1", "f518"), ("f516", "1"), ("f519", "f520"), ("f521", "1"), ("1", "f503"), ("f523", "1"), ("1", "f524"), ("f522", "1"), ("f525", "f526"), ("1", "1"), ("f528", "1"), ("1", "f529"), ("1", "a1"), ("f531", "1"), ("1", "f532"), ("1", "b2"), ("f534", "1"), ("1", "f535"), ("1", "f530"), ("f537", "1"), ("1", "f538"), ("f539", "b2"), ("1", "f533"), ("f541", "1"), ("1", "f542"), ("f540", "1"), ("f543", "f544"), ("f545", "1"), ("1", "1"), ("f547", "1"), ("1", "f548"), ("1", "b1"), ("f550", "1"), ("1", "f551"), ("1", "a2"), ("f553", "1"), ("1", "f554"), ("1", "f549"), ("f556", "1"), ("1", "f557"), ("f558", "a2"), ("1", "f552"), ("f560", "1"), ("1", "f561"), ("f559", "1"), ("f562", "f563"), ("f564", "1"), ("1", "1"), ("f566", "1"), ("1", "f567"), ("1", "f568"), ("f569", "1"), ("1", "f570"), ("f565", "1"), ("f571", "f572"), ("1", "f546"), ("f574", "1"), ("1", "f575"), ("f573", "1"), ("f576", "f577"), ("1", "1"), ("f579", "1"), ("1", "f580"), ("1", "c1"), ("f582", "1"), ("1", "f583"), ("1", "d2"), ("f585", "1"), ("1", "f586"), ("1", "f581"), ("f588", "1"), ("1", "f589"), ("f590", "d2"), ("1", "f584"), ("f592", "1"), ("1", "f593"), ("f591", "1"), ("f594", "f595"), ("f596", "1"), ("1", "1"), ("f598", "1"), ("1", "f599"), ("1", "f600"), ("f601", "1"), ("1", "f602"), ("f597", "1"), ("f603", "f604"), ("1", "f578"), ("f606", "1"), ("1", "f607"), ("f605", "1"), ("f608", "f609"), ("1", "1"), ("f611", "1"), ("1", "f612"), ("1", "d1"), ("f614", "1"), ("1", "f615"), ("1", "c2"), ("f617", "1"), ("1", "f618"), ("1", "f613"), ("f620", "1"), ("1", "f621"), ("f622", "c2"), ("1", "f616"), ("f624", "1"), ("1", "f625"), ("f623", "1"), ("f626", "f627"), ("f628", "1"), ("1", "f610"), ("f630", "1"), ("1", "f631"), ("f629", "1"), ("f632", "f633"), ("1", "1"), ("f635", "1"), ("1", "f636"), ("1", "a1"), ("f638", "1"), ("1", "f639"), ("1", "c2"), ("f641", "1"), ("1", "f642"), ("1", "f637"), ("f644", "1"), ("1", "f645"), ("f646", "c2"), ("1", "f640"), ("f648", "1"), ("1", "f649"), ("f647", "1"), ("f650", "f651"), ("f652", "1"), ("1", "1"), ("f654", "1"), ("1", "f655"), ("1", "b1"), ("f657", "1"), ("1", "f658"), ("1", "d2"), ("f660", "1"), ("1", "f661"), ("1", "f656"), ("f663", "1"), ("1", "f664"), ("f665", "d2"), ("1", "f659"), ("f667", "1"), ("1", "f668"), ("f666", "1"), ("f669", "f670"), ("f671", "1"), ("1", "f653"), ("f673", "1"), ("1", "f674"), ("f672", "1"), ("f675", "f676"), ("1", "1"), ("f678", "1"), ("1", "f679"), ("1", "c1"), ("f681", "1"), ("1", "f682"), ("1", "a2"), ("f684", "1"), ("1", "f685"), ("1", "f680"), ("f687", "1"), ("1", "f688"), ("f689", "a2"), ("1", "f683"), ("f691", "1"), ("1", "f692"), ("f690", "1"), ("f693", "f694"), ("f695", "1"), ("1", "1"), ("f697", "1"), ("1", "f698"), ("1", "f699"), ("f700", "1"), ("1", "f701"), ("f696", "1"), ("f702", "f703"), ("1", "f677"), ("f705", "1"), ("1", "f706"), ("f704", "1"), ("f707", "f708"), ("1", "1"), ("f710", "1"), ("1", "f711"), ("1", "d1"), ("f713", "1"), ("1", "f714"), ("1", "b2"), ("f716", "1"), ("1", "f717"), ("1", "f712"), ("f719", "1"), ("1", "f720"), ("f721", "b2"), ("1", "f715"), ("f723", "1"), ("1", "f724"), ("f722", "1"), ("f725", "f726"), ("f727", "1"), ("1", "1"), ("f729", "1"), ("1", "f730"), ("1", "f731"), ("f732", "1"), ("1", "f733"), ("f728", "1"), ("f734", "f735"), ("1", "f709"), ("f737", "1"), ("1", "f738"), ("f736", "1"), ("f739", "f740"), ("1", "1"), ("f742", "1"), ("1", "f743"), ("1", "a1"), ("f745", "1"), ("1", "f746"), ("1", "a2"), ("f748", "1"), ("1", "f749"), ("1", "f744"), ("f751", "1"), ("1", "f752"), ("f753", "a2"), ("1", "f747"), ("f755", "1"), ("1", "f756"), ("f754", "1"), ("f757", "f758"), ("f759", "1"), ("1", "1"), ("f761", "1"), ("1", "f762"), ("1", "b1"), ("f764", "1"), ("1", "f765"), ("1", "b2"), ("f767", "1"), ("1", "f768"), ("1", "f763"), ("f770", "1"), ("1", "f771"), ("f772", "b2"), ("1", "f766"), ("f774", "1"), ("1", "f775"), ("f773", "1"), ("f776", "f777"), ("f778", "1"), ("1", "1"), ("f780", "1"), ("1", "f781"), ("1", "c1"), ("f783", "1"), ("1", "f784"), ("1", "c2"), ("f786", "1"), ("1", "f787"), ("1", "f782"), ("f789", "1"), ("1", "f790"), ("f791", "c2"), ("1", "f785"), ("f793", "1"), ("1", "f794"), ("f792", "1"), ("f795", "f796"), ("f797", "1"), ("1", "1"), ("f799", "1"), ("1", "f800"), ("1", "f801"), ("f802", "1"), ("1", "f803"), ("f798", "1"), ("f804", "f805"), ("1", "f779"), ("f807", "1"), ("1", "f808"), ("f806", "1"), ("f809", "f810"), ("1", "1"), ("f812", "1"), ("1", "f813"), ("1", "d1"), ("f815", "1"), ("1", "f816"), ("1", "d2"), ("f818", "1"), ("1", "f819"), ("1", "f814"), ("f821", "1"), ("1", "f822"), ("f823", "d2"), ("1", "f817"), ("f825", "1"), ("1", "f826"), ("f824", "1"), ("f827", "f828"), ("f829", "1"), ("1", "1"), ("f831", "1"), ("1", "f832"), ("1", "f833"), ("f834", "1"), ("1", "f835"), ("f830", "1"), ("f836", "f837"), ("1", "f811"), ("f839", "1"), ("1", "f840"), ("f838", "1"), ("f841", "f842"), ("1", "f760"), ("f844", "1"), ("1", "f845"), ("f843", "1"), ("f846", "f847"), ("1", "1"), ("f849", "1"), ("1", "f850"), ("1", "a1"), ("f852", "1"), ("1", "f853"), ("1", "b2"), ("f855", "1"), ("1", "f856"), ("1", "f851"), ("f858", "1"), ("1", "f859"), ("f860", "b2"), ("1", "f854"), ("f862", "1"), ("1", "f863"), ("f861", "1"), ("f864", "f865"), ("f866", "1"), ("1", "1"), ("f868", "1"), ("1", "f869"), ("1", "b1"), ("f871", "1"), ("1", "f872"), ("1", "a2"), ("f874", "1"), ("1", "f875"), ("1", "f870"), ("f877", "1"), ("1", "f878"), ("f879", "a2"), ("1", "f873"), ("f881", "1"), ("1", "f882"), ("f880", "1"), ("f883", "f884"), ("f885", "1"), ("1", "1"), ("f887", "1"), ("1", "f888"), ("1", "f889"), ("f890", "1"), ("1", "f891"), ("f886", "1"), ("f892", "f893"), ("1", "f867"), ("f895", "1"), ("1", "f896"), ("f894", "1"), ("f897", "f898"), ("1", "1"), ("f900", "1"), ("1", "f901"), ("1", "d1"), ("f903", "1"), ("1", "f904"), ("1", "c2"), ("f906", "1"), ("1", "f907"), ("1", "f902"), ("f909", "1"), ("1", "f910"), ("f911", "c2"), ("1", "f905"), ("f913", "1"), ("1", "f914"), ("f912", "1"), ("f915", "f916"), ("f917", "1"), ("1", "1"), ("f919", "1"), ("1", "f920"), ("1", "c1"), ("f922", "1"), ("1", "f923"), ("1", "d2"), ("f925", "1"), ("1", "f926"), ("1", "f921"), ("f928", "1"), ("1", "f929"), ("f930", "d2"), ("1", "f924"), ("f932", "1"), ("1", "f933"), ("f931", "1"), ("f934", "f935"), ("f936", "1"), ("1", "f918"), ("f938", "1"), ("1", "f939"), ("f937", "1"), ("f940", "f941"), ("1", "f899"), ("f943", "1"), ("1", "f944"), ("f942", "1"), ("f945", "f946")],
        },
        ParametricChain {
            variables: &["a1", "b1", "c1", "d1", "a2", "b2", "c2", "d2"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a1"), ("f4", "1"), ("1", "f5"), ("1", "a2"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "a2"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b1"), ("f23", "1"), ("1", "f24"), ("1", "b2"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b2"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42"), ("1", "1"), ("f44", "1"), ("1", "f45"), ("1", "c1"), ("f47", "1"), ("1", "f48"), ("1", "c2"), ("f50", "1"), ("1", "f51"), ("1", "f46"), ("f53", "1"), ("1", "f54"), ("f55", "c2"), ("1", "f49"), ("f57", "1"), ("1", "f58"), ("f56", "1"), ("f59", "f60"), ("f61", "1"), ("1", "f43"), ("f63", "1"), ("1", "f64"), ("f62", "1"), ("f65", "f66"), ("1", "1"), ("f68", "1"), ("1", "f69"), ("1", "d1"), ("f71", "1"), ("1", "f72"), ("1", "d2"), ("f74", "1"), ("1", "f75"), ("1", "f70"), ("f77", "1"), ("1", "f78"), ("f79", "d2"), ("1", "f73"), ("f81", "1"), ("1", "f82"), ("f80", "1"), ("f83", "f84"), ("f85", "1"), ("1", "f67"), ("f87", "1"), ("1", "f88"), ("f86", "1"), ("f89", "f90"), ("1", "1"), ("f92", "1"), ("1", "f93"), ("1", "a1"), ("f95", "1"), ("1", "f96"), ("1", "b2"), ("f98", "1"), ("1", "f99"), ("1", "f94"), ("f101", "1"), ("1", "f102"), ("f103", "b2"), ("1", "f97"), ("f105", "1"), ("1", "f106"), ("f104", "1"), ("f107", "f108"), ("f109", "1"), ("1", "1"), ("f111", "1"), ("1", "f112"), ("1", "a2"), ("f114", "1"), ("1", "f115"), ("1", "b1"), ("f117", "1"), ("1", "f118"), ("1", "f113"), ("f120", "1"), ("1", "f121"), ("f122", "b1"), ("1", "f116"), ("f124", "1"), ("1", "f125"), ("f123", "1"), ("f126", "f127"), ("f128", "1"), ("1", "f110"), ("f130", "1"), ("1", "f131"), ("f129", "1"), ("f132", "f133"), ("1", "1"), ("f135", "1"), ("1", "f136"), ("1", "c1"), ("f138", "1"), ("1", "f139"), ("1", "d2"), ("f141", "1"), ("1", "f142"), ("1", "f137"), ("f144", "1"), ("1", "f145"), ("f146", "d2"), ("1", "f140"), ("f148", "1"), ("1", "f149"), ("f147", "1"), ("f150", "f151"), ("f152", "1"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "f156"), ("f157", "1"), ("1", "f158"), ("f153", "1"), ("f159", "f160"), ("1", "f134"), ("f162", "1"), ("1", "f163"), ("f161", "1"), ("f164", "f165"), ("1", "1"), ("f167", "1"), ("1", "f168"), ("1", "d1"), ("f170", "1"), ("1", "f171"), ("1", "c2"), ("f173", "1"), ("1", "f174"), ("1", "f169"), ("f176", "1"), ("1", "f177"), ("f178", "c2"), ("1", "f172"), ("f180", "1"), ("1", "f181"), ("f179", "1"), ("f182", "f183"), ("f184", "1"), ("1", "1"), ("f186", "1"), ("1", "f187"), ("1", "f188"), ("f189", "1"), ("1", "f190"), ("f185", "1"), ("f191", "f192"), ("1", "1"), ("f194", "1"), ("1", "f195"), ("1", "f196"), ("f197", "1"), ("1", "f198"), ("f193", "1"), ("f199", "f200"), ("1", "f166"), ("f202", "1"), ("1", "f203"), ("f201", "1"), ("f204", "f205"), ("1", "1"), ("f207", "1"), ("1", "f208"), ("1", "a1"), ("f210", "1"), ("1", "f211"), ("1", "c2"), ("f213", "1"), ("1", "f214"), ("1", "f209"), ("f216", "1"), ("1", "f217"), ("f218", "c2"), ("1", "f212"), ("f220", "1"), ("1", "f221"), ("f219", "1"), ("f222", "f223"), ("f224", "1"), ("1", "1"), ("f226", "1"), ("1", "f227"), ("1", "c1"), ("f229", "1"), ("1", "f230"), ("1", "a2"), ("f232", "1"), ("1", "f233"), ("1", "f228"), ("f235", "1"), ("1", "f236"), ("f237", "a2"), ("1", "f231"), ("f239", "1"), ("1", "f240"), ("f238", "1"), ("f241", "f242"), ("f243", "1"), ("1", "f225"), ("f245", "1"), ("1", "f246"), ("f244", "1"), ("f247", "f248"), ("1", "1"), ("f250", "1"), ("1", "f251"), ("1", "d1"), ("f253", "1"), ("1", "f254"), ("1", "b2"), ("f256", "1"), ("1", "f257"), ("1", "f252"), ("f259", "1"), ("1", "f260"), ("f261", "b2"), ("1", "f255"), ("f263", "1"), ("1", "f264"), ("f262", "1"), ("f265", "f266"), ("f267", "1"), ("1", "1"), ("f269", "1"), ("1", "f270"), ("1", "f271"), ("f272", "1"), ("1", "f273"), ("f268", "1"), ("f274", "f275"), ("1", "f249"), ("f277", "1"), ("1", "f278"), ("f276", "1"), ("f279", "f280"), ("1", "1"), ("f282", "1"), ("1", "f283"), ("1", "b1"), ("f285", "1"), ("1", "f286"), ("1", "d2"), ("f288", "1"), ("1", "f289"), ("1", "f284"), ("f291", "1"), ("1", "f292"), ("f293", "d2"), ("1", "f287"), ("f295", "1"), ("1", "f296"), ("f294", "1"), ("f297", "f298"), ("f299", "1"), ("1", "1"), ("f301", "1"), ("1", "f302"), ("1", "f303"), ("f304", "1"), ("1", "f305"), ("f300", "1"), ("f306", "f307"), ("1", "1"), ("f309", "1"), ("1", "f310"), ("1", "f311"), ("f312", "1"), ("1", "f313"), ("f308", "1"), ("f314", "f315"), ("1", "f281"), ("f317", "1"), ("1", "f318"), ("f316", "1"), ("f319", "f320"), ("1", "1"), ("f322", "1"), ("1", "f323"), ("1", "a1"), ("f325", "1"), ("1", "f326"), ("1", "d2"), ("f328", "1"), ("1", "f329"), ("1", "f324"), ("f331", "1"), ("1", "f332"), ("f333", "d2"), ("1", "f327"), ("f335", "1"), ("1", "f336"), ("f334", "1"), ("f337", "f338"), ("f339", "1"), ("1", "1"), ("f341", "1"), ("1", "f342"), ("1", "d1"), ("f344", "1"), ("1", "f345"), ("1", "a2"), ("f347", "1"), ("1", "f348"), ("1", "f343"), ("f350", "1"), ("1", "f351"), ("f352", "a2"), ("1", "f346"), ("f354", "1"), ("1", "f355"), ("f353", "1"), ("f356", "f357"), ("f358", "1"), ("1", "f340"), ("f360", "1"), ("1", "f361"), ("f359", "1"), ("f362", "f363"), ("1", "1"), ("f365", "1"), ("1", "f366"), ("1", "b1"), ("f368", "1"), ("1", "f369"), ("1", "c2"), ("f371", "1"), ("1", "f372"), ("1", "f367"), ("f374", "1"), ("1", "f375"), ("f376", "c2"), ("1", "f370"), ("f378", "1"), ("1", "f379"), ("f377", "1"), ("f380", "f381"), ("f382", "1"), ("1", "1"), ("f384", "1"), ("1", "f385"), ("1", "f386"), ("f387", "1"), ("1", "f388"), ("f383", "1"), ("f389", "f390"), ("1", "f364"), ("f392", "1"), ("1", "f393"), ("f391", "1"), ("f394", "f395"), ("1", "1"), ("f397", "1"), ("1", "f398"), ("1", "c1"), ("f400", "1"), ("1", "f401"), ("1", "b2"), ("f403", "1"), ("1", "f404"), ("1", "f399"), ("f406", "1"), ("1", "f407"), ("f408", "b2"), ("1", "f402"), ("f410", "1"), ("1", "f411"), ("f409", "1"), ("f412", "f413"), ("f414", "1"), ("1", "1"), ("f416", "1"), ("1", "f417"), ("1", "f418"), ("f419", "1"), ("1", "f420"), ("f415", "1"), ("f421", "f422"), ("1", "1"), ("f424", "1"), ("1", "f425"), ("1", "f426"), ("f427", "1"), ("1", "f428"), ("f423", "1"), ("f429", "f430"), ("1", "f396"), ("f432", "1"), ("1", "f433"), ("f431", "1"), ("f434", "f435"), ("1", "1"), ("f437", "1"), ("1", "f438"), ("1", "a1"), ("f440", "1"), ("1", "f441"), ("1", "a2"), ("f443", "1"), ("1", "f444"), ("1", "f439"), ("f446", "1"), ("1", "f447"), ("f448", "a2"), ("1", "f442"), ("f450", "1"), ("1", "f451"), ("f449", "1"), ("f452", "f453"), ("f454", "1"), ("1", "1"), ("f456", "1"), ("1", "f457"), ("1", "b1"), ("f459", "1"), ("1", "f460"), ("1", "b2"), ("f462", "1"), ("1", "f463"), ("1", "f458"), ("f465", "1"), ("1", "f466"), ("f467", "b2"), ("1", "f461"), ("f469", "1"), ("1", "f470"), ("f468", "1"), ("f471", "f472"), ("f473", "1"), ("1", "f455"), ("f475", "1"), ("1", "f476"), ("f474", "1"), ("f477", "f478"), ("1", "1"), ("f480", "1"), ("1", "f481"), ("1", "c1"), ("f483", "1"), ("1", "f484"), ("1", "c2"), ("f486", "1"), ("1", "f487"), ("1", "f482"), ("f489", "1"), ("1", "f490"), ("f491", "c2"), ("1", "f485"), ("f493", "1"), ("1", "f494"), ("f492", "1"), ("f495", "f496"), ("f497", "1"), ("1", "f479"), ("f499", "1"), ("1", "f500"), ("f498", "1"), ("f501", "f502"), ("1", "1"), ("f504", "1"), ("1", "f505"), ("1", "d1"), ("f507", "1"), ("1", "f508"), ("1", "d2"), ("f510", "1"), ("1", "f511"), ("1", "f506"), ("f513", "1"), ("1", "f514"), ("f515", "d2"), ("1", "f509"), ("f517", "1"), ("1", "f518"), ("f516", "1"), ("f519", "f520"), ("f521", "1"), ("1", "f503"), ("f523", "1"), ("1", "f524"), ("f522", "1"), ("f525", "f526"), ("1", "1"), ("f528", "1"), ("1", "f529"), ("1", "a1"), ("f531", "1"), ("1", "f532"), ("1", "b2"), ("f534", "1"), ("1", "f535"), ("1", "f530"), ("f537", "1"), ("1", "f538"), ("f539", "b2"), ("1", "f533"), ("f541", "1"), ("1", "f542"), ("f540", "1"), ("f543", "f544"), ("f545", "1"), ("1", "1"), ("f547", "1"), ("1", "f548"), ("1", "b1"), ("f550", "1"), ("1", "f551"), ("1", "a2"), ("f553", "1"), ("1", "f554"), ("1", "f549"), ("f556", "1"), ("1", "f557"), ("f558", "a2"), ("1", "f552"), ("f560", "1"), ("1", "f561"), ("f559", "1"), ("f562", "f563"), ("f564", "1"), ("1", "1"), ("f566", "1"), ("1", "f567"), ("1", "f568"), ("f569", "1"), ("1", "f570"), ("f565", "1"), ("f571", "f572"), ("1", "f546"), ("f574", "1"), ("1", "f575"), ("f573", "1"), ("f576", "f577"), ("1", "1"), ("f579", "1"), ("1", "f580"), ("1", "c1"), ("f582", "1"), ("1", "f583"), ("1", "d2"), ("f585", "1"), ("1", "f586"), ("1", "f581"), ("f588", "1"), ("1", "f589"), ("f590", "d2"), ("1", "f584"), ("f592", "1"), ("1", "f593"), ("f591", "1"), ("f594", "f595"), ("f596", "1"), ("1", "1"), ("f598", "1"), ("1", "f599"), ("1", "f600"), ("f601", "1"), ("1", "f602"), ("f597", "1"), ("f603", "f604"), ("1", "f578"), ("f606", "1"), ("1", "f607"), ("f605", "1"), ("f608", "f609"), ("1", "1"), ("f611", "1"), ("1", "f612"), ("1", "d1"), ("f614", "1"), ("1", "f615"), ("1", "c2"), ("f617", "1"), ("1", "f618"), ("1", "f613"), ("f620", "1"), ("1", "f621"), ("f622", "c2"), ("1", "f616"), ("f624", "1"), ("1", "f625"), ("f623", "1"), ("f626", "f627"), ("f628", "1"), ("1", "f610"), ("f630", "1"), ("1", "f631"), ("f629", "1"), ("f632", "f633"), ("1", "1"), ("f635", "1"), ("1", "f636"), ("1", "a1"), ("f638", "1"), ("1", "f639"), ("1", "c2"), ("f641", "1"), ("1", "f642"), ("1", "f637"), ("f644", "1"), ("1", "f645"), ("f646", "c2"), ("1", "f640"), ("f648", "1"), ("1", "f649"), ("f647", "1"), ("f650", "f651"), ("f652", "1"), ("1", "1"), ("f654", "1"), ("1", "f655"), ("1", "b1"), ("f657", "1"), ("1", "f658"), ("1", "d2"), ("f660", "1"), ("1", "f661"), ("1", "f656"), ("f663", "1"), ("1", "f664"), ("f665", "d2"), ("1", "f659"), ("f667", "1"), ("1", "f668"), ("f666", "1"), ("f669", "f670"), ("f671", "1"), ("1", "f653"), ("f673", "1"), ("1", "f674"), ("f672", "1"), ("f675", "f676"), ("1", "1"), ("f678", "1"), ("1", "f679"), ("1", "c1"), ("f681", "1"), ("1", "f682"), ("1", "a2"), ("f684", "1"), ("1", "f685"), ("1", "f680"), ("f687", "1"), ("1", "f688"), ("f689", "a2"), ("1", "f683"), ("f691", "1"), ("1", "f692"), ("f690", "1"), ("f693", "f694"), ("f695", "1"), ("1", "1"), ("f697", "1"), ("1", "f698"), ("1", "f699"), ("f700", "1"), ("1", "f701"), ("f696", "1"), ("f702", "f703"), ("1", "f677"), ("f705", "1"), ("1", "f706"), ("f704", "1"), ("f707", "f708"), ("1", "1"), ("f710", "1"), ("1", "f711"), ("1", "d1"), ("f713", "1"), ("1", "f714"), ("1", "b2"), ("f716", "1"), ("1", "f717"), ("1", "f712"), ("f719", "1"), ("1", "f720"), ("f721", "b2"), ("1", "f715"), ("f723", "1"), ("1", "f724"), ("f722", "1"), ("f725", "f726"), ("f727", "1"), ("1", "1"), ("f729", "1"), ("1", "f730"), ("1", "f731"), ("f732", "1"), ("1", "f733"), ("f728", "1"), ("f734", "f735"), ("1", "f709"), ("f737", "1"), ("1", "f738"), ("f736", "1"), ("f739", "f740"), ("1", "1"), ("f742", "1"), ("1", "f743"), ("1", "a1"), ("f745", "1"), ("1", "f746"), ("1", "a2"), ("f748", "1"), ("1", "f749"), ("1", "f744"), ("f751", "1"), ("1", "f752"), ("f753", "a2"), ("1", "f747"), ("f755", "1"), ("1", "f756"), ("f754", "1"), ("f757", "f758"), ("f759", "1"), ("1", "1"), ("f761", "1"), ("1", "f762"), ("1", "b1"), ("f764", "1"), ("1", "f765"), ("1", "b2"), ("f767", "1"), ("1", "f768"), ("1", "f763"), ("f770", "1"), ("1", "f771"), ("f772", "b2"), ("1", "f766"), ("f774", "1"), ("1", "f775"), ("f773", "1"), ("f776", "f777"), ("f778", "1"), ("1", "1"), ("f780", "1"), ("1", "f781"), ("1", "c1"), ("f783", "1"), ("1", "f784"), ("1", "c2"), ("f786", "1"), ("1", "f787"), ("1", "f782"), ("f789", "1"), ("1", "f790"), ("f791", "c2"), ("1", "f785"), ("f793", "1"), ("1", "f794"), ("f792", "1"), ("f795", "f796"), ("f797", "1"), ("1", "1"), ("f799", "1"), ("1", "f800"), ("1", "f801"), ("f802", "1"), ("1", "f803"), ("f798", "1"), ("f804", "f805"), ("1", "f779"), ("f807", "1"), ("1", "f808"), ("f806", "1"), ("f809", "f810"), ("1", "1"), ("f812", "1"), ("1", "f813"), ("1", "d1"), ("f815", "1"), ("1", "f816"), ("1", "d2"), ("f818", "1"), ("1", "f819"), ("1", "f814"), ("f821", "1"), ("1", "f822"), ("f823", "d2"), ("1", "f817"), ("f825", "1"), ("1", "f826"), ("f824", "1"), ("f827", "f828"), ("f829", "1"), ("1", "1"), ("f831", "1"), ("1", "f832"), ("1", "f833"), ("f834", "1"), ("1", "f835"), ("f830", "1"), ("f836", "f837"), ("1", "f811"), ("f839", "1"), ("1", "f840"), ("f838", "1"), ("f841", "f842"), ("1", "f760"), ("f844", "1"), ("1", "f845"), ("f843", "1"), ("f846", "f847"), ("1", "1"), ("f849", "1"), ("1", "f850"), ("1", "a1"), ("f852", "1"), ("1", "f853"), ("1", "b2"), ("f855", "1"), ("1", "f856"), ("1", "f851"), ("f858", "1"), ("1", "f859"), ("f860", "b2"), ("1", "f854"), ("f862", "1"), ("1", "f863"), ("f861", "1"), ("f864", "f865"), ("f866", "1"), ("1", "1"), ("f868", "1"), ("1", "f869"), ("1", "b1"), ("f871", "1"), ("1", "f872"), ("1", "a2"), ("f874", "1"), ("1", "f875"), ("1", "f870"), ("f877", "1"), ("1", "f878"), ("f879", "a2"), ("1", "f873"), ("f881", "1"), ("1", "f882"), ("f880", "1"), ("f883", "f884"), ("f885", "1"), ("1", "1"), ("f887", "1"), ("1", "f888"), ("1", "f889"), ("f890", "1"), ("1", "f891"), ("f886", "1"), ("f892", "f893"), ("1", "f867"), ("f895", "1"), ("1", "f896"), ("f894", "1"), ("f897", "f898"), ("1", "1"), ("f900", "1"), ("1", "f901"), ("1", "d1"), ("f903", "1"), ("1", "f904"), ("1", "c2"), ("f906", "1"), ("1", "f907"), ("1", "f902"), ("f909", "1"), ("1", "f910"), ("f911", "c2"), ("1", "f905"), ("f913", "1"), ("1", "f914"), ("f912", "1"), ("f915", "f916"), ("f917", "1"), ("1", "1"), ("f919", "1"), ("1", "f920"), ("1", "c1"), ("f922", "1"), ("1", "f923"), ("1", "d2"), ("f925", "1"), ("1", "f926"), ("1", "f921"), ("f928", "1"), ("1", "f929"), ("f930", "d2"), ("1", "f924"), ("f932", "1"), ("1", "f933"), ("f931", "1"), ("f934", "f935"), ("f936", "1"), ("1", "f918"), ("f938", "1"), ("1", "f939"), ("f937", "1"), ("f940", "f941"), ("1", "f899"), ("f943", "1"), ("1", "f944"), ("f942", "1"), ("f945", "f946"), ("1", "1"), ("f948", "1"), ("1", "f949"), ("1", "a1"), ("f951", "1"), ("1", "f952"), ("1", "c2"), ("f954", "1"), ("1", "f955"), ("1", "f950"), ("f957", "1"), ("1", "f958"), ("f959", "c2"), ("1", "f953"), ("f961", "1"), ("1", "f962"), ("f960", "1"), ("f963", "f964"), ("f965", "1"), ("1", "1"), ("f967", "1"), ("1", "f968"), ("1", "c1"), ("f970", "1"), ("1", "f971"), ("1", "a2"), ("f973", "1"), ("1", "f974"), ("1", "f969"), ("f976", "1"), ("1", "f977"), ("f978", "a2"), ("1", "f972"), ("f980", "1"), ("1", "f981"), ("f979", "1"), ("f982", "f983"), ("f984", "1"), ("1", "1"), ("f986", "1"), ("1", "f987"), ("1", "f988"), ("f989", "1"), ("1", "f990"), ("f985", "1"), ("f991", "f992"), ("1", "f966"), ("f994", "1"), ("1", "f995"), ("f993", "1"), ("f996", "f997"), ("1", "1"), ("f999", "1"), ("1", "f1000"), ("1", "b1"), ("f1002", "1"), ("1", "f1003"), ("1", "d2"), ("f1005", "1"), ("1", "f1006"), ("1", "f1001"), ("f1008", "1"), ("1", "f1009"), ("f1010", "d2"), ("1", "f1004"), ("f1012", "1"), ("1", "f1013"), ("f1011", "1"), ("f1014", "f1015"), ("f1016", "1"), ("1", "1"), ("f1018", "1"), ("1", "f1019"), ("1", "d1"), ("f1021", "1"), ("1", "f1022"), ("1", "b2"), ("f1024", "1"), ("1", "f1025"), ("1", "f1020"), ("f1027", "1"), ("1", "f1028"), ("f1029", "b2"), ("1", "f1023"), ("f1031", "1"), ("1", "f1032"), ("f1030", "1"), ("f1033", "f1034"), ("f1035", "1"), ("1", "f1017"), ("f1037", "1"), ("1", "f1038"), ("f1036", "1"), ("f1039", "f1040"), ("1", "f998"), ("f1042", "1"), ("1", "f1043"), ("f1041", "1"), ("f1044", "f1045")],
        },
        ParametricChain {
            variables: &["a1", "b1", "c1", "d1", "a2", "b2", "c2", "d2"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "a1"), ("f4", "1"), ("1", "f5"), ("1", "a2"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "a2"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "b1"), ("f23", "1"), ("1", "f24"), ("1", "b2"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "b2"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "f19"), ("f39", "1"), ("1", "f40"), ("f38", "1"), ("f41", "f42"), ("1", "1"), ("f44", "1"), ("1", "f45"), ("1", "c1"), ("f47", "1"), ("1", "f48"), ("1", "c2"), ("f50", "1"), ("1", "f51"), ("1", "f46"), ("f53", "1"), ("1", "f54"), ("f55", "c2"), ("1", "f49"), ("f57", "1"), ("1", "f58"), ("f56", "1"), ("f59", "f60"), ("f61", "1"), ("1", "f43"), ("f63", "1"), ("1", "f64"), ("f62", "1"), ("f65", "f66"), ("1", "1"), ("f68", "1"), ("1", "f69"), ("1", "d1"), ("f71", "1"), ("1", "f72"), ("1", "d2"), ("f74", "1"), ("1", "f75"), ("1", "f70"), ("f77", "1"), ("1", "f78"), ("f79", "d2"), ("1", "f73"), ("f81", "1"), ("1", "f82"), ("f80", "1"), ("f83", "f84"), ("f85", "1"), ("1", "f67"), ("f87", "1"), ("1", "f88"), ("f86", "1"), ("f89", "f90"), ("1", "1"), ("f92", "1"), ("1", "f93"), ("1", "a1"), ("f95", "1"), ("1", "f96"), ("1", "b2"), ("f98", "1"), ("1", "f99"), ("1", "f94"), ("f101", "1"), ("1", "f102"), ("f103", "b2"), ("1", "f97"), ("f105", "1"), ("1", "f106"), ("f104", "1"), ("f107", "f108"), ("f109", "1"), ("1", "1"), ("f111", "1"), ("1", "f112"), ("1", "a2"), ("f114", "1"), ("1", "f115"), ("1", "b1"), ("f117", "1"), ("1", "f118"), ("1", "f113"), ("f120", "1"), ("1", "f121"), ("f122", "b1"), ("1", "f116"), ("f124", "1"), ("1", "f125"), ("f123", "1"), ("f126", "f127"), ("f128", "1"), ("1", "f110"), ("f130", "1"), ("1", "f131"), ("f129", "1"), ("f132", "f133"), ("1", "1"), ("f135", "1"), ("1", "f136"), ("1", "c1"), ("f138", "1"), ("1", "f139"), ("1", "d2"), ("f141", "1"), ("1", "f142"), ("1", "f137"), ("f144", "1"), ("1", "f145"), ("f146", "d2"), ("1", "f140"), ("f148", "1"), ("1", "f149"), ("f147", "1"), ("f150", "f151"), ("f152", "1"), ("1", "1"), ("f154", "1"), ("1", "f155"), ("1", "f156"), ("f157", "1"), ("1", "f158"), ("f153", "1"), ("f159", "f160"), ("1", "f134"), ("f162", "1"), ("1", "f163"), ("f161", "1"), ("f164", "f165"), ("1", "1"), ("f167", "1"), ("1", "f168"), ("1", "d1"), ("f170", "1"), ("1", "f171"), ("1", "c2"), ("f173", "1"), ("1", "f174"), ("1", "f169"), ("f176", "1"), ("1", "f177"), ("f178", "c2"), ("1", "f172"), ("f180", "1"), ("1", "f181"), ("f179", "1"), ("f182", "f183"), ("f184", "1"), ("1", "1"), ("f186", "1"), ("1", "f187"), ("1", "f188"), ("f189", "1"), ("1", "f190"), ("f185", "1"), ("f191", "f192"), ("1", "1"), ("f194", "1"), ("1", "f195"), ("1", "f196"), ("f197", "1"), ("1", "f198"), ("f193", "1"), ("f199", "f200"), ("1", "f166"), ("f202", "1"), ("1", "f203"), ("f201", "1"), ("f204", "f205"), ("1", "1"), ("f207", "1"), ("1", "f208"), ("1", "a1"), ("f210", "1"), ("1", "f211"), ("1", "c2"), ("f213", "1"), ("1", "f214"), ("1", "f209"), ("f216", "1"), ("1", "f217"), ("f218", "c2"), ("1", "f212"), ("f220", "1"), ("1", "f221"), ("f219", "1"), ("f222", "f223"), ("f224", "1"), ("1", "1"), ("f226", "1"), ("1", "f227"), ("1", "c1"), ("f229", "1"), ("1", "f230"), ("1", "a2"), ("f232", "1"), ("1", "f233"), ("1", "f228"), ("f235", "1"), ("1", "f236"), ("f237", "a2"), ("1", "f231"), ("f239", "1"), ("1", "f240"), ("f238", "1"), ("f241", "f242"), ("f243", "1"), ("1", "f225"), ("f245", "1"), ("1", "f246"), ("f244", "1"), ("f247", "f248"), ("1", "1"), ("f250", "1"), ("1", "f251"), ("1", "d1"), ("f253", "1"), ("1", "f254"), ("1", "b2"), ("f256", "1"), ("1", "f257"), ("1", "f252"), ("f259", "1"), ("1", "f260"), ("f261", "b2"), ("1", "f255"), ("f263", "1"), ("1", "f264"), ("f262", "1"), ("f265", "f266"), ("f267", "1"), ("1", "1"), ("f269", "1"), ("1", "f270"), ("1", "f271"), ("f272", "1"), ("1", "f273"), ("f268", "1"), ("f274", "f275"), ("1", "f249"), ("f277", "1"), ("1", "f278"), ("f276", "1"), ("f279", "f280"), ("1", "1"), ("f282", "1"), ("1", "f283"), ("1", "b1"), ("f285", "1"), ("1", "f286"), ("1", "d2"), ("f288", "1"), ("1", "f289"), ("1", "f284"), ("f291", "1"), ("1", "f292"), ("f293", "d2"), ("1", "f287"), ("f295", "1"), ("1", "f296"), ("f294", "1"), ("f297", "f298"), ("f299", "1"), ("1", "1"), ("f301", "1"), ("1", "f302"), ("1", "f303"), ("f304", "1"), ("1", "f305"), ("f300", "1"), ("f306", "f307"), ("1", "1"), ("f309", "1"), ("1", "f310"), ("1", "f311"), ("f312", "1"), ("1", "f313"), ("f308", "1"), ("f314", "f315"), ("1", "f281"), ("f317", "1"), ("1", "f318"), ("f316", "1"), ("f319", "f320"), ("1", "1"), ("f322", "1"), ("1", "f323"), ("1", "a1"), ("f325", "1"), ("1", "f326"), ("1", "d2"), ("f328", "1"), ("1", "f329"), ("1", "f324"), ("f331", "1"), ("1", "f332"), ("f333", "d2"), ("1", "f327"), ("f335", "1"), ("1", "f336"), ("f334", "1"), ("f337", "f338"), ("f339", "1"), ("1", "1"), ("f341", "1"), ("1", "f342"), ("1", "d1"), ("f344", "1"), ("1", "f345"), ("1", "a2"), ("f347", "1"), ("1", "f348"), ("1", "f343"), ("f350", "1"), ("1", "f351"), ("f352", "a2"), ("1", "f346"), ("f354", "1"), ("1", "f355"), ("f353", "1"), ("f356", "f357"), ("f358", "1"), ("1", "f340"), ("f360", "1"), ("1", "f361"), ("f359", "1"), ("f362", "f363"), ("1", "1"), ("f365", "1"), ("1", "f366"), ("1", "b1"), ("f368", "1"), ("1", "f369"), ("1", "c2"), ("f371", "1"), ("1", "f372"), ("1", "f367"), ("f374", "1"), ("1", "f375"), ("f376", "c2"), ("1", "f370"), ("f378", "1"), ("1", "f379"), ("f377", "1"), ("f380", "f381"), ("f382", "1"), ("1", "1"), ("f384", "1"), ("1", "f385"), ("1", "f386"), ("f387", "1"), ("1", "f388"), ("f383", "1"), ("f389", "f390"), ("1", "f364"), ("f392", "1"), ("1", "f393"), ("f391", "1"), ("f394", "f395"), ("1", "1"), ("f397", "1"), ("1", "f398"), ("1", "c1"), ("f400", "1"), ("1", "f401"), ("1", "b2"), ("f403", "1"), ("1", "f404"), ("1", "f399"), ("f406", "1"), ("1", "f407"), ("f408", "b2"), ("1", "f402"), ("f410", "1"), ("1", "f411"), ("f409", "1"), ("f412", "f413"), ("f414", "1"), ("1", "1"), ("f416", "1"), ("1", "f417"), ("1", "f418"), ("f419", "1"), ("1", "f420"), ("f415", "1"), ("f421", "f422"), ("1", "1"), ("f424", "1"), ("1", "f425"), ("1", "f426"), ("f427", "1"), ("1", "f428"), ("f423", "1"), ("f429", "f430"), ("1", "f396"), ("f432", "1"), ("1", "f433"), ("f431", "1"), ("f434", "f435"), ("1", "1"), ("f437", "1"), ("1", "f438"), ("1", "a1"), ("f440", "1"), ("1", "f441"), ("1", "a2"), ("f443", "1"), ("1", "f444"), ("1", "f439"), ("f446", "1"), ("1", "f447"), ("f448", "a2"), ("1", "f442"), ("f450", "1"), ("1", "f451"), ("f449", "1"), ("f452", "f453"), ("f454", "1"), ("1", "1"), ("f456", "1"), ("1", "f457"), ("1", "b1"), ("f459", "1"), ("1", "f460"), ("1", "b2"), ("f462", "1"), ("1", "f463"), ("1", "f458"), ("f465", "1"), ("1", "f466"), ("f467", "b2"), ("1", "f461"), ("f469", "1"), ("1", "f470"), ("f468", "1"), ("f471", "f472"), ("f473", "1"), ("1", "f455"), ("f475", "1"), ("1", "f476"), ("f474", "1"), ("f477", "f478"), ("1", "1"), ("f480", "1"), ("1", "f481"), ("1", "c1"), ("f483", "1"), ("1", "f484"), ("1", "c2"), ("f486", "1"), ("1", "f487"), ("1", "f482"), ("f489", "1"), ("1", "f490"), ("f491", "c2"), ("1", "f485"), ("f493", "1"), ("1", "f494"), ("f492", "1"), ("f495", "f496"), ("f497", "1"), ("1", "f479"), ("f499", "1"), ("1", "f500"), ("f498", "1"), ("f501", "f502"), ("1", "1"), ("f504", "1"), ("1", "f505"), ("1", "d1"), ("f507", "1"), ("1", "f508"), ("1", "d2"), ("f510", "1"), ("1", "f511"), ("1", "f506"), ("f513", "1"), ("1", "f514"), ("f515", "d2"), ("1", "f509"), ("f517", "1"), ("1", "f518"), ("f516", "1"), ("f519", "f520"), ("f521", "1"), ("1", "f503"), ("f523", "1"), ("1", "f524"), ("f522", "1"), ("f525", "f526"), ("1", "1"), ("f528", "1"), ("1", "f529"), ("1", "a1"), ("f531", "1"), ("1", "f532"), ("1", "b2"), ("f534", "1"), ("1", "f535"), ("1", "f530"), ("f537", "1"), ("1", "f538"), ("f539", "b2"), ("1", "f533"), ("f541", "1"), ("1", "f542"), ("f540", "1"), ("f543", "f544"), ("f545", "1"), ("1", "1"), ("f547", "1"), ("1", "f548"), ("1", "b1"), ("f550", "1"), ("1", "f551"), ("1", "a2"), ("f553", "1"), ("1", "f554"), ("1", "f549"), ("f556", "1"), ("1", "f557"), ("f558", "a2"), ("1", "f552"), ("f560", "1"), ("1", "f561"), ("f559", "1"), ("f562", "f563"), ("f564", "1"), ("1", "1"), ("f566", "1"), ("1", "f567"), ("1", "f568"), ("f569", "1"), ("1", "f570"), ("f565", "1"), ("f571", "f572"), ("1", "f546"), ("f574", "1"), ("1", "f575"), ("f573", "1"), ("f576", "f577"), ("1", "1"), ("f579", "1"), ("1", "f580"), ("1", "c1"), ("f582", "1"), ("1", "f583"), ("1", "d2"), ("f585", "1"), ("1", "f586"), ("1", "f581"), ("f588", "1"), ("1", "f589"), ("f590", "d2"), ("1", "f584"), ("f592", "1"), ("1", "f593"), ("f591", "1"), ("f594", "f595"), ("f596", "1"), ("1", "1"), ("f598", "1"), ("1", "f599"), ("1", "f600"), ("f601", "1"), ("1", "f602"), ("f597", "1"), ("f603", "f604"), ("1", "f578"), ("f606", "1"), ("1", "f607"), ("f605", "1"), ("f608", "f609"), ("1", "1"), ("f611", "1"), ("1", "f612"), ("1", "d1"), ("f614", "1"), ("1", "f615"), ("1", "c2"), ("f617", "1"), ("1", "f618"), ("1", "f613"), ("f620", "1"), ("1", "f621"), ("f622", "c2"), ("1", "f616"), ("f624", "1"), ("1", "f625"), ("f623", "1"), ("f626", "f627"), ("f628", "1"), ("1", "f610"), ("f630", "1"), ("1", "f631"), ("f629", "1"), ("f632", "f633"), ("1", "1"), ("f635", "1"), ("1", "f636"), ("1", "a1"), ("f638", "1"), ("1", "f639"), ("1", "c2"), ("f641", "1"), ("1", "f642"), ("1", "f637"), ("f644", "1"), ("1", "f645"), ("f646", "c2"), ("1", "f640"), ("f648", "1"), ("1", "f649"), ("f647", "1"), ("f650", "f651"), ("f652", "1"), ("1", "1"), ("f654", "1"), ("1", "f655"), ("1", "b1"), ("f657", "1"), ("1", "f658"), ("1", "d2"), ("f660", "1"), ("1", "f661"), ("1", "f656"), ("f663", "1"), ("1", "f664"), ("f665", "d2"), ("1", "f659"), ("f667", "1"), ("1", "f668"), ("f666", "1"), ("f669", "f670"), ("f671", "1"), ("1", "f653"), ("f673", "1"), ("1", "f674"), ("f672", "1"), ("f675", "f676"), ("1", "1"), ("f678", "1"), ("1", "f679"), ("1", "c1"), ("f681", "1"), ("1", "f682"), ("1", "a2"), ("f684", "1"), ("1", "f685"), ("1", "f680"), ("f687", "1"), ("1", "f688"), ("f689", "a2"), ("1", "f683"), ("f691", "1"), ("1", "f692"), ("f690", "1"), ("f693", "f694"), ("f695", "1"), ("1", "1"), ("f697", "1"), ("1", "f698"), ("1", "f699"), ("f700", "1"), ("1", "f701"), ("f696", "1"), ("f702", "f703"), ("1", "f677"), ("f705", "1"), ("1", "f706"), ("f704", "1"), ("f707", "f708"), ("1", "1"), ("f710", "1"), ("1", "f711"), ("1", "d1"), ("f713", "1"), ("1", "f714"), ("1", "b2"), ("f716", "1"), ("1", "f717"), ("1", "f712"), ("f719", "1"), ("1", "f720"), ("f721", "b2"), ("1", "f715"), ("f723", "1"), ("1", "f724"), ("f722", "1"), ("f725", "f726"), ("f727", "1"), ("1", "1"), ("f729", "1"), ("1", "f730"), ("1", "f731"), ("f732", "1"), ("1", "f733"), ("f728", "1"), ("f734", "f735"), ("1", "f709"), ("f737", "1"), ("1", "f738"), ("f736", "1"), ("f739", "f740"), ("1", "1"), ("f742", "1"), ("1", "f743"), ("1", "a1"), ("f745", "1"), ("1", "f746"), ("1", "a2"), ("f748", "1"), ("1", "f749"), ("1", "f744"), ("f751", "1"), ("1", "f752"), ("f753", "a2"), ("1", "f747"), ("f755", "1"), ("1", "f756"), ("f754", "1"), ("f757", "f758"), ("f759", "1"), ("1", "1"), ("f761", "1"), ("1", "f762"), ("1", "b1"), ("f764", "1"), ("1", "f765"), ("1", "b2"), ("f767", "1"), ("1", "f768"), ("1", "f763"), ("f770", "1"), ("1", "f771"), ("f772", "b2"), ("1", "f766"), ("f774", "1"), ("1", "f775"), ("f773", "1"), ("f776", "f777"), ("f778", "1"), ("1", "1"), ("f780", "1"), ("1", "f781"), ("1", "c1"), ("f783", "1"), ("1", "f784"), ("1", "c2"), ("f786", "1"), ("1", "f787"), ("1", "f782"), ("f789", "1"), ("1", "f790"), ("f791", "c2"), ("1", "f785"), ("f793", "1"), ("1", "f794"), ("f792", "1"), ("f795", "f796"), ("f797", "1"), ("1", "1"), ("f799", "1"), ("1", "f800"), ("1", "f801"), ("f802", "1"), ("1", "f803"), ("f798", "1"), ("f804", "f805"), ("1", "f779"), ("f807", "1"), ("1", "f808"), ("f806", "1"), ("f809", "f810"), ("1", "1"), ("f812", "1"), ("1", "f813"), ("1", "d1"), ("f815", "1"), ("1", "f816"), ("1", "d2"), ("f818", "1"), ("1", "f819"), ("1", "f814"), ("f821", "1"), ("1", "f822"), ("f823", "d2"), ("1", "f817"), ("f825", "1"), ("1", "f826"), ("f824", "1"), ("f827", "f828"), ("f829", "1"), ("1", "1"), ("f831", "1"), ("1", "f832"), ("1", "f833"), ("f834", "1"), ("1", "f835"), ("f830", "1"), ("f836", "f837"), ("1", "f811"), ("f839", "1"), ("1", "f840"), ("f838", "1"), ("f841", "f842"), ("1", "f760"), ("f844", "1"), ("1", "f845"), ("f843", "1"), ("f846", "f847"), ("1", "1"), ("f849", "1"), ("1", "f850"), ("1", "a1"), ("f852", "1"), ("1", "f853"), ("1", "b2"), ("f855", "1"), ("1", "f856"), ("1", "f851"), ("f858", "1"), ("1", "f859"), ("f860", "b2"), ("1", "f854"), ("f862", "1"), ("1", "f863"), ("f861", "1"), ("f864", "f865"), ("f866", "1"), ("1", "1"), ("f868", "1"), ("1", "f869"), ("1", "b1"), ("f871", "1"), ("1", "f872"), ("1", "a2"), ("f874", "1"), ("1", "f875"), ("1", "f870"), ("f877", "1"), ("1", "f878"), ("f879", "a2"), ("1", "f873"), ("f881", "1"), ("1", "f882"), ("f880", "1"), ("f883", "f884"), ("f885", "1"), ("1", "1"), ("f887", "1"), ("1", "f888"), ("1", "f889"), ("f890", "1"), ("1", "f891"), ("f886", "1"), ("f892", "f893"), ("1", "f867"), ("f895", "1"), ("1", "f896"), ("f894", "1"), ("f897", "f898"), ("1", "1"), ("f900", "1"), ("1", "f901"), ("1", "d1"), ("f903", "1"), ("1", "f904"), ("1", "c2"), ("f906", "1"), ("1", "f907"), ("1", "f902"), ("f909", "1"), ("1", "f910"), ("f911", "c2"), ("1", "f905"), ("f913", "1"), ("1", "f914"), ("f912", "1"), ("f915", "f916"), ("f917", "1"), ("1", "1"), ("f919", "1"), ("1", "f920"), ("1", "c1"), ("f922", "1"), ("1", "f923"), ("1", "d2"), ("f925", "1"), ("1", "f926"), ("1", "f921"), ("f928", "1"), ("1", "f929"), ("f930", "d2"), ("1", "f924"), ("f932", "1"), ("1", "f933"), ("f931", "1"), ("f934", "f935"), ("f936", "1"), ("1", "f918"), ("f938", "1"), ("1", "f939"), ("f937", "1"), ("f940", "f941"), ("1", "f899"), ("f943", "1"), ("1", "f944"), ("f942", "1"), ("f945", "f946"), ("1", "1"), ("f948", "1"), ("1", "f949"), ("1", "a1"), ("f951", "1"), ("1", "f952"), ("1", "c2"), ("f954", "1"), ("1", "f955"), ("1", "f950"), ("f957", "1"), ("1", "f958"), ("f959", "c2"), ("1", "f953"), ("f961", "1"), ("1", "f962"), ("f960", "1"), ("f963", "f964"), ("f965", "1"), ("1", "1"), ("f967", "1"), ("1", "f968"), ("1", "c1"), ("f970", "1"), ("1", "f971"), ("1", "a2"), ("f973", "1"), ("1", "f974"), ("1", "f969"), ("f976", "1"), ("1", "f977"), ("f978", "a2"), ("1", "f972"), ("f980", "1"), ("1", "f981"), ("f979", "1"), ("f982", "f983"), ("f984", "1"), ("1", "1"), ("f986", "1"), ("1", "f987"), ("1", "f988"), ("f989", "1"), ("1", "f990"), ("f985", "1"), ("f991", "f992"), ("1", "f966"), ("f994", "1"), ("1", "f995"), ("f993", "1"), ("f996", "f997"), ("1", "1"), ("f999", "1"), ("1", "f1000"), ("1", "b1"), ("f1002", "1"), ("1", "f1003"), ("1", "d2"), ("f1005", "1"), ("1", "f1006"), ("1", "f1001"), ("f1008", "1"), ("1", "f1009"), ("f1010", "d2"), ("1", "f1004"), ("f1012", "1"), ("1", "f1013"), ("f1011", "1"), ("f1014", "f1015"), ("f1016", "1"), ("1", "1"), ("f1018", "1"), ("1", "f1019"), ("1", "d1"), ("f1021", "1"), ("1", "f1022"), ("1", "b2"), ("f1024", "1"), ("1", "f1025"), ("1", "f1020"), ("f1027", "1"), ("1", "f1028"), ("f1029", "b2"), ("1", "f1023"), ("f1031", "1"), ("1", "f1032"), ("f1030", "1"), ("f1033", "f1034"), ("f1035", "1"), ("1", "f1017"), ("f1037", "1"), ("1", "f1038"), ("f1036", "1"), ("f1039", "f1040"), ("1", "f998"), ("f1042", "1"), ("1", "f1043"), ("f1041", "1"), ("f1044", "f1045"), ("1", "1"), ("f1047", "1"), ("1", "f1048"), ("1", "a1"), ("f1050", "1"), ("1", "f1051"), ("1", "d2"), ("f1053", "1"), ("1", "f1054"), ("1", "f1049"), ("f1056", "1"), ("1", "f1057"), ("f1058", "d2"), ("1", "f1052"), ("f1060", "1"), ("1", "f1061"), ("f1059", "1"), ("f1062", "f1063"), ("f1064", "1"), ("1", "1"), ("f1066", "1"), ("1", "f1067"), ("1", "d1"), ("f1069", "1"), ("1", "f1070"), ("1", "a2"), ("f1072", "1"), ("1", "f1073"), ("1", "f1068"), ("f1075", "1"), ("1", "f1076"), ("f1077", "a2"), ("1", "f1071"), ("f1079", "1"), ("1", "f1080"), ("f1078", "1"), ("f1081", "f1082"), ("f1083", "1"), ("1", "1"), ("f1085", "1"), ("1", "f1086"), ("1", "f1087"), ("f1088", "1"), ("1", "f1089"), ("f1084", "1"), ("f1090", "f1091"), ("1", "f1065"), ("f1093", "1"), ("1", "f1094"), ("f1092", "1"), ("f1095", "f1096"), ("1", "1"), ("f1098", "1"), ("1", "f1099"), ("1", "c1"), ("f1101", "1"), ("1", "f1102"), ("1", "b2"), ("f1104", "1"), ("1", "f1105"), ("1", "f1100"), ("f1107", "1"), ("1", "f1108"), ("f1109", "b2"), ("1", "f1103"), ("f1111", "1"), ("1", "f1112"), ("f1110", "1"), ("f1113", "f1114"), ("f1115", "1"), ("1", "1"), ("f1117", "1"), ("1", "f1118"), ("1", "b1"), ("f1120", "1"), ("1", "f1121"), ("1", "c2"), ("f1123", "1"), ("1", "f1124"), ("1", "f1119"), ("f1126", "1"), ("1", "f1127"), ("f1128", "c2"), ("1", "f1122"), ("f1130", "1"), ("1", "f1131"), ("f1129", "1"), ("f1132", "f1133"), ("f1134", "1"), ("1", "f1116"), ("f1136", "1"), ("1", "f1137"), ("f1135", "1"), ("f1138", "f1139"), ("1", "f1097"), ("f1141", "1"), ("1", "f1142"), ("f1140", "1"), ("f1143", "f1144")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "quaternion multiplication",
    },
    MacroDefinition {
        shorthand_id: "RCC",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["t", "tau", "V0", "one"],
            levels: &[("1", "t"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("f6", "tau"), ("f7", "1"), ("1", "1"), ("f9", "1"), ("1", "f10"), ("1", "f11"), ("f12", "1"), ("1", "f13"), ("f8", "1"), ("f14", "f15"), ("f16", "1"), ("1", "one"), ("f18", "1"), ("1", "f19"), ("f17", "1"), ("f20", "f21"), ("1", "1"), ("f23", "1"), ("1", "f24"), ("1", "V0"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("1", "f25"), ("f32", "1"), ("1", "f33"), ("f34", "f22"), ("1", "f28"), ("f36", "1"), ("1", "f37"), ("f35", "1"), ("f38", "f39"), ("f40", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "RC charging V0*(1 - exp(-t/tau))",
    },
    MacroDefinition {
        shorthand_id: "REN",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["gamma", "m", "c_sq"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "m"), ("f4", "1"), ("1", "f5"), ("1", "c_sq"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "c_sq"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "gamma"), ("f23", "1"), ("1", "f24"), ("1", "f19"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "f19"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "relativistic energy gamma * m * c^2",
    },
    MacroDefinition {
        shorthand_id: "RLC",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::EnvelopeBounded,
        chain_templates: &[
        ParametricChain {
            variables: &["L", "C", "neg_half"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "L"), ("f4", "1"), ("1", "f5"), ("1", "C"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "C"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "f19"), ("f20", "1"), ("1", "f21"), ("1", "1"), ("f23", "1"), ("1", "f24"), ("1", "neg_half"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("1", "f25"), ("f32", "1"), ("1", "f33"), ("f34", "f22"), ("1", "f28"), ("f36", "1"), ("1", "f37"), ("f35", "1"), ("f38", "f39"), ("f40", "1"), ("f41", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::EnvelopeBounded,
        envelope_bound: Some(EnvelopeBound {
        bound_value: 1.0,
        spec_paragraph_ref: "",
        description: "RLC resonance frequency 1/sqrt(LC); envelope-limited at small LC where intermediate ln intermediate falls outside evaluator clamp",
    }),
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::SeparateEnvelopeCorpus,
        description: "RLC resonance frequency (envelope-limited; LC > 1)",
    },
    MacroDefinition {
        shorthand_id: "RLU",
        function_class: FunctionClass::NnActivation,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "half"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "x"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "f19"), ("f20", "1"), ("1", "f21"), ("1", "1"), ("f23", "1"), ("1", "f24"), ("1", "half"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("1", "f25"), ("f32", "1"), ("1", "f33"), ("f34", "f22"), ("1", "f28"), ("f36", "1"), ("1", "f37"), ("f35", "1"), ("f38", "f39"), ("f40", "1"), ("f41", "1"), ("1", "1"), ("f43", "1"), ("1", "f44"), ("1", "f45"), ("f46", "1"), ("1", "f47"), ("f42", "1"), ("f48", "f49"), ("1", "x"), ("f51", "1"), ("1", "f52"), ("f50", "1"), ("f53", "f54"), ("1", "1"), ("f56", "1"), ("1", "f57"), ("1", "f55"), ("f59", "1"), ("1", "f60"), ("1", "half"), ("f62", "1"), ("1", "f63"), ("1", "f58"), ("f65", "1"), ("1", "f66"), ("f67", "half"), ("1", "f61"), ("f69", "1"), ("1", "f70"), ("f68", "1"), ("f71", "f72"), ("f73", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "ReLU(x) = (x+|x|)/2",
    },
    MacroDefinition {
        shorthand_id: "RRT",
        function_class: FunctionClass::Trigonometric,
        variant_tag: VariantTag::SenderPreprocessed,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "x"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "x"), ("f23", "1"), ("1", "f24"), ("1", "f19"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "f19"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f38"), ("f42", "1"), ("1", "f43"), ("1", "f19"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "f19"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f57"), ("f61", "1"), ("1", "f62"), ("1", "f19"), ("f64", "1"), ("1", "f65"), ("1", "f60"), ("f67", "1"), ("1", "f68"), ("f69", "f19"), ("1", "f63"), ("f71", "1"), ("1", "f72"), ("f70", "1"), ("f73", "f74"), ("f75", "1"), ("1", "1"), ("f77", "1"), ("1", "f78"), ("1", "f76"), ("f80", "1"), ("1", "f81"), ("1", "f19"), ("f83", "1"), ("1", "f84"), ("1", "f79"), ("f86", "1"), ("1", "f87"), ("f88", "f19"), ("1", "f82"), ("f90", "1"), ("1", "f91"), ("f89", "1"), ("f92", "f93"), ("f94", "1"), ("1", "1"), ("f96", "1"), ("1", "f97"), ("1", "f95"), ("f99", "1"), ("1", "f100"), ("1", "f19"), ("f102", "1"), ("1", "f103"), ("1", "f98"), ("f105", "1"), ("1", "f106"), ("f107", "f19"), ("1", "f101"), ("f109", "1"), ("1", "f110"), ("f108", "1"), ("f111", "f112"), ("f113", "1"), ("1", "1"), ("f115", "1"), ("1", "f116"), ("1", "f114"), ("f118", "1"), ("1", "f119"), ("1", "f19"), ("f121", "1"), ("1", "f122"), ("1", "f117"), ("f124", "1"), ("1", "f125"), ("f126", "f19"), ("1", "f120"), ("f128", "1"), ("1", "f129"), ("f127", "1"), ("f130", "f131"), ("f132", "1"), ("1", "x"), ("f134", "1"), ("1", "f135"), ("1", "f136"), ("f137", "1"), ("1", "f138"), ("f139", "1"), ("f140", "1"), ("1", "1"), ("f142", "1"), ("1", "f143"), ("1", "f141"), ("f145", "1"), ("1", "f146"), ("1", "1"), ("f148", "1"), ("1", "f149"), ("1", "f144"), ("f151", "1"), ("1", "f152"), ("f153", "1"), ("1", "f147"), ("f155", "1"), ("1", "f156"), ("f154", "1"), ("f157", "f158"), ("f159", "1"), ("1", "1"), ("f161", "1"), ("1", "f162"), ("1", "f163"), ("f164", "1"), ("1", "f165"), ("f160", "1"), ("f166", "f167"), ("1", "1"), ("f169", "1"), ("1", "f170"), ("f168", "1"), ("f171", "f172"), ("1", "f38"), ("f174", "1"), ("1", "f175"), ("1", "f176"), ("f177", "1"), ("1", "f178"), ("f179", "1"), ("f180", "1"), ("1", "1"), ("f182", "1"), ("1", "f183"), ("1", "f181"), ("f185", "1"), ("1", "f186"), ("1", "1"), ("f188", "1"), ("1", "f189"), ("1", "f184"), ("f191", "1"), ("1", "f192"), ("f193", "1"), ("1", "f187"), ("f195", "1"), ("1", "f196"), ("f194", "1"), ("f197", "f198"), ("f199", "1"), ("1", "1"), ("f201", "1"), ("1", "f202"), ("1", "f203"), ("f204", "1"), ("1", "f205"), ("f200", "1"), ("f206", "f207"), ("1", "f173"), ("f209", "1"), ("1", "f210"), ("f208", "1"), ("f211", "f212"), ("1", "f57"), ("f214", "1"), ("1", "f215"), ("1", "f216"), ("f217", "1"), ("1", "f218"), ("f219", "1"), ("f220", "1"), ("1", "1"), ("f222", "1"), ("1", "f223"), ("1", "f221"), ("f225", "1"), ("1", "f226"), ("1", "1"), ("f228", "1"), ("1", "f229"), ("1", "f224"), ("f231", "1"), ("1", "f232"), ("f233", "1"), ("1", "f227"), ("f235", "1"), ("1", "f236"), ("f234", "1"), ("f237", "f238"), ("f239", "1"), ("1", "1"), ("f241", "1"), ("1", "f242"), ("1", "f243"), ("f244", "1"), ("1", "f245"), ("f240", "1"), ("f246", "f247"), ("1", "f213"), ("f249", "1"), ("1", "f250"), ("f248", "1"), ("f251", "f252"), ("1", "f76"), ("f254", "1"), ("1", "f255"), ("1", "f256"), ("f257", "1"), ("1", "f258"), ("f259", "1"), ("f260", "1"), ("1", "1"), ("f262", "1"), ("1", "f263"), ("1", "f261"), ("f265", "1"), ("1", "f266"), ("1", "1"), ("f268", "1"), ("1", "f269"), ("1", "f264"), ("f271", "1"), ("1", "f272"), ("f273", "1"), ("1", "f267"), ("f275", "1"), ("1", "f276"), ("f274", "1"), ("f277", "f278"), ("f279", "1"), ("1", "1"), ("f281", "1"), ("1", "f282"), ("1", "f283"), ("f284", "1"), ("1", "f285"), ("f280", "1"), ("f286", "f287"), ("1", "f253"), ("f289", "1"), ("1", "f290"), ("f288", "1"), ("f291", "f292"), ("1", "f95"), ("f294", "1"), ("1", "f295"), ("1", "f296"), ("f297", "1"), ("1", "f298"), ("f299", "1"), ("f300", "1"), ("1", "1"), ("f302", "1"), ("1", "f303"), ("1", "f301"), ("f305", "1"), ("1", "f306"), ("1", "1"), ("f308", "1"), ("1", "f309"), ("1", "f304"), ("f311", "1"), ("1", "f312"), ("f313", "1"), ("1", "f307"), ("f315", "1"), ("1", "f316"), ("f314", "1"), ("f317", "f318"), ("f319", "1"), ("1", "1"), ("f321", "1"), ("1", "f322"), ("1", "f323"), ("f324", "1"), ("1", "f325"), ("f320", "1"), ("f326", "f327"), ("1", "f293"), ("f329", "1"), ("1", "f330"), ("f328", "1"), ("f331", "f332"), ("1", "f114"), ("f334", "1"), ("1", "f335"), ("1", "f336"), ("f337", "1"), ("1", "f338"), ("f339", "1"), ("f340", "1"), ("1", "1"), ("f342", "1"), ("1", "f343"), ("1", "f341"), ("f345", "1"), ("1", "f346"), ("1", "1"), ("f348", "1"), ("1", "f349"), ("1", "f344"), ("f351", "1"), ("1", "f352"), ("f353", "1"), ("1", "f347"), ("f355", "1"), ("1", "f356"), ("f354", "1"), ("f357", "f358"), ("f359", "1"), ("1", "1"), ("f361", "1"), ("1", "f362"), ("1", "f363"), ("f364", "1"), ("1", "f365"), ("f360", "1"), ("f366", "f367"), ("1", "f333"), ("f369", "1"), ("1", "f370"), ("f368", "1"), ("f371", "f372"), ("1", "f133"), ("f374", "1"), ("1", "f375"), ("1", "f376"), ("f377", "1"), ("1", "f378"), ("f379", "1"), ("f380", "1"), ("1", "1"), ("f382", "1"), ("1", "f383"), ("1", "f381"), ("f385", "1"), ("1", "f386"), ("1", "1"), ("f388", "1"), ("1", "f389"), ("1", "f384"), ("f391", "1"), ("1", "f392"), ("f393", "1"), ("1", "f387"), ("f395", "1"), ("1", "f396"), ("f394", "1"), ("f397", "f398"), ("f399", "1"), ("1", "1"), ("f401", "1"), ("1", "f402"), ("1", "f403"), ("f404", "1"), ("1", "f405"), ("f400", "1"), ("f406", "f407"), ("1", "f373"), ("f409", "1"), ("1", "f410"), ("f408", "1"), ("f411", "f412")],
        },
    ],
        preprocessing: Some("modulo_2pi_full_domain"),
        postprocessing: Some("apply_quadrant_sign_for_sin"),
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "range-reduced sin (K1 protocol; full-domain modulo 2pi at sender)",
    },
    MacroDefinition {
        shorthand_id: "SCH",
        function_class: FunctionClass::Trigonometric,
        variant_tag: VariantTag::SenderPreprocessed,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "x"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "x"), ("f23", "1"), ("1", "f24"), ("1", "f19"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "f19"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f38"), ("f42", "1"), ("1", "f43"), ("1", "f19"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "f19"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f57"), ("f61", "1"), ("1", "f62"), ("1", "f19"), ("f64", "1"), ("1", "f65"), ("1", "f60"), ("f67", "1"), ("1", "f68"), ("f69", "f19"), ("1", "f63"), ("f71", "1"), ("1", "f72"), ("f70", "1"), ("f73", "f74"), ("f75", "1"), ("1", "1"), ("f77", "1"), ("1", "f78"), ("1", "f76"), ("f80", "1"), ("1", "f81"), ("1", "f19"), ("f83", "1"), ("1", "f84"), ("1", "f79"), ("f86", "1"), ("1", "f87"), ("f88", "f19"), ("1", "f82"), ("f90", "1"), ("1", "f91"), ("f89", "1"), ("f92", "f93"), ("f94", "1"), ("1", "1"), ("f96", "1"), ("1", "f97"), ("1", "f95"), ("f99", "1"), ("1", "f100"), ("1", "f19"), ("f102", "1"), ("1", "f103"), ("1", "f98"), ("f105", "1"), ("1", "f106"), ("f107", "f19"), ("1", "f101"), ("f109", "1"), ("1", "f110"), ("f108", "1"), ("f111", "f112"), ("f113", "1"), ("1", "1"), ("f115", "1"), ("1", "f116"), ("1", "f114"), ("f118", "1"), ("1", "f119"), ("1", "f19"), ("f121", "1"), ("1", "f122"), ("1", "f117"), ("f124", "1"), ("1", "f125"), ("f126", "f19"), ("1", "f120"), ("f128", "1"), ("1", "f129"), ("f127", "1"), ("f130", "f131"), ("f132", "1"), ("1", "1"), ("f134", "1"), ("1", "f135"), ("1", "f133"), ("f137", "1"), ("1", "f138"), ("1", "f19"), ("f140", "1"), ("1", "f141"), ("1", "f136"), ("f143", "1"), ("1", "f144"), ("f145", "f19"), ("1", "f139"), ("f147", "1"), ("1", "f148"), ("f146", "1"), ("f149", "f150"), ("f151", "1"), ("1", "1"), ("f153", "1"), ("1", "f154"), ("1", "f152"), ("f156", "1"), ("1", "f157"), ("1", "f19"), ("f159", "1"), ("1", "f160"), ("1", "f155"), ("f162", "1"), ("1", "f163"), ("f164", "f19"), ("1", "f158"), ("f166", "1"), ("1", "f167"), ("f165", "1"), ("f168", "f169"), ("f170", "1"), ("1", "1"), ("f172", "1"), ("1", "f173"), ("1", "f171"), ("f175", "1"), ("1", "f176"), ("1", "f19"), ("f178", "1"), ("1", "f179"), ("1", "f174"), ("f181", "1"), ("1", "f182"), ("f183", "f19"), ("1", "f177"), ("f185", "1"), ("1", "f186"), ("f184", "1"), ("f187", "f188"), ("f189", "1"), ("1", "1"), ("f191", "1"), ("1", "f192"), ("1", "f190"), ("f194", "1"), ("1", "f195"), ("1", "f19"), ("f197", "1"), ("1", "f198"), ("1", "f193"), ("f200", "1"), ("1", "f201"), ("f202", "f19"), ("1", "f196"), ("f204", "1"), ("1", "f205"), ("f203", "1"), ("f206", "f207"), ("f208", "1"), ("1", "x"), ("f210", "1"), ("1", "f211"), ("1", "f212"), ("f213", "1"), ("1", "f214"), ("f215", "1"), ("f216", "1"), ("1", "1"), ("f218", "1"), ("1", "f219"), ("1", "f217"), ("f221", "1"), ("1", "f222"), ("1", "1"), ("f224", "1"), ("1", "f225"), ("1", "f220"), ("f227", "1"), ("1", "f228"), ("f229", "1"), ("1", "f223"), ("f231", "1"), ("1", "f232"), ("f230", "1"), ("f233", "f234"), ("f235", "1"), ("1", "1"), ("f237", "1"), ("1", "f238"), ("1", "f239"), ("f240", "1"), ("1", "f241"), ("f236", "1"), ("f242", "f243"), ("1", "1"), ("f245", "1"), ("1", "f246"), ("f244", "1"), ("f247", "f248"), ("1", "f38"), ("f250", "1"), ("1", "f251"), ("1", "f252"), ("f253", "1"), ("1", "f254"), ("f255", "1"), ("f256", "1"), ("1", "1"), ("f258", "1"), ("1", "f259"), ("1", "f257"), ("f261", "1"), ("1", "f262"), ("1", "1"), ("f264", "1"), ("1", "f265"), ("1", "f260"), ("f267", "1"), ("1", "f268"), ("f269", "1"), ("1", "f263"), ("f271", "1"), ("1", "f272"), ("f270", "1"), ("f273", "f274"), ("f275", "1"), ("1", "1"), ("f277", "1"), ("1", "f278"), ("1", "f279"), ("f280", "1"), ("1", "f281"), ("f276", "1"), ("f282", "f283"), ("1", "f249"), ("f285", "1"), ("1", "f286"), ("f284", "1"), ("f287", "f288"), ("1", "f57"), ("f290", "1"), ("1", "f291"), ("1", "f292"), ("f293", "1"), ("1", "f294"), ("f295", "1"), ("f296", "1"), ("1", "1"), ("f298", "1"), ("1", "f299"), ("1", "f297"), ("f301", "1"), ("1", "f302"), ("1", "1"), ("f304", "1"), ("1", "f305"), ("1", "f300"), ("f307", "1"), ("1", "f308"), ("f309", "1"), ("1", "f303"), ("f311", "1"), ("1", "f312"), ("f310", "1"), ("f313", "f314"), ("f315", "1"), ("1", "1"), ("f317", "1"), ("1", "f318"), ("1", "f319"), ("f320", "1"), ("1", "f321"), ("f316", "1"), ("f322", "f323"), ("1", "f289"), ("f325", "1"), ("1", "f326"), ("f324", "1"), ("f327", "f328"), ("1", "f76"), ("f330", "1"), ("1", "f331"), ("1", "f332"), ("f333", "1"), ("1", "f334"), ("f335", "1"), ("f336", "1"), ("1", "1"), ("f338", "1"), ("1", "f339"), ("1", "f337"), ("f341", "1"), ("1", "f342"), ("1", "1"), ("f344", "1"), ("1", "f345"), ("1", "f340"), ("f347", "1"), ("1", "f348"), ("f349", "1"), ("1", "f343"), ("f351", "1"), ("1", "f352"), ("f350", "1"), ("f353", "f354"), ("f355", "1"), ("1", "1"), ("f357", "1"), ("1", "f358"), ("1", "f359"), ("f360", "1"), ("1", "f361"), ("f356", "1"), ("f362", "f363"), ("1", "f329"), ("f365", "1"), ("1", "f366"), ("f364", "1"), ("f367", "f368"), ("1", "f95"), ("f370", "1"), ("1", "f371"), ("1", "f372"), ("f373", "1"), ("1", "f374"), ("f375", "1"), ("f376", "1"), ("1", "1"), ("f378", "1"), ("1", "f379"), ("1", "f377"), ("f381", "1"), ("1", "f382"), ("1", "1"), ("f384", "1"), ("1", "f385"), ("1", "f380"), ("f387", "1"), ("1", "f388"), ("f389", "1"), ("1", "f383"), ("f391", "1"), ("1", "f392"), ("f390", "1"), ("f393", "f394"), ("f395", "1"), ("1", "1"), ("f397", "1"), ("1", "f398"), ("1", "f399"), ("f400", "1"), ("1", "f401"), ("f396", "1"), ("f402", "f403"), ("1", "f369"), ("f405", "1"), ("1", "f406"), ("f404", "1"), ("f407", "f408"), ("1", "f114"), ("f410", "1"), ("1", "f411"), ("1", "f412"), ("f413", "1"), ("1", "f414"), ("f415", "1"), ("f416", "1"), ("1", "1"), ("f418", "1"), ("1", "f419"), ("1", "f417"), ("f421", "1"), ("1", "f422"), ("1", "1"), ("f424", "1"), ("1", "f425"), ("1", "f420"), ("f427", "1"), ("1", "f428"), ("f429", "1"), ("1", "f423"), ("f431", "1"), ("1", "f432"), ("f430", "1"), ("f433", "f434"), ("f435", "1"), ("1", "1"), ("f437", "1"), ("1", "f438"), ("1", "f439"), ("f440", "1"), ("1", "f441"), ("f436", "1"), ("f442", "f443"), ("1", "f409"), ("f445", "1"), ("1", "f446"), ("f444", "1"), ("f447", "f448"), ("1", "f133"), ("f450", "1"), ("1", "f451"), ("1", "f452"), ("f453", "1"), ("1", "f454"), ("f455", "1"), ("f456", "1"), ("1", "1"), ("f458", "1"), ("1", "f459"), ("1", "f457"), ("f461", "1"), ("1", "f462"), ("1", "1"), ("f464", "1"), ("1", "f465"), ("1", "f460"), ("f467", "1"), ("1", "f468"), ("f469", "1"), ("1", "f463"), ("f471", "1"), ("1", "f472"), ("f470", "1"), ("f473", "f474"), ("f475", "1"), ("1", "1"), ("f477", "1"), ("1", "f478"), ("1", "f479"), ("f480", "1"), ("1", "f481"), ("f476", "1"), ("f482", "f483"), ("1", "f449"), ("f485", "1"), ("1", "f486"), ("f484", "1"), ("f487", "f488")],
        },
    ],
        preprocessing: Some("modulo_2pi_with_quadrant"),
        postprocessing: Some("apply_quadrant_sign_for_sin"),
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "sin Chebyshev-equivalent (degree-11 polynomial; principal-domain after sender preproc)",
    },
    MacroDefinition {
        shorthand_id: "SHR",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["R_p", "R_f", "sigma"],
            levels: &[("1", "R_p"), ("f1", "1"), ("1", "f2"), ("R_f", "1"), ("f3", "f4"), ("1", "f5"), ("f6", "1"), ("1", "f7"), ("1", "f8"), ("f9", "1"), ("1", "f10"), ("f11", "sigma"), ("f12", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Sharpe ratio (R_p - R_f)/sigma",
    },
    MacroDefinition {
        shorthand_id: "SIG",
        function_class: FunctionClass::NnActivation,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("x", "1"), ("f6", "f7"), ("f8", "1"), ("1", "1"), ("f10", "1"), ("1", "f11"), ("1", "f12"), ("f13", "1"), ("1", "f14"), ("f9", "1"), ("f15", "f16"), ("1", "1"), ("f18", "1"), ("1", "f19"), ("f17", "1"), ("f20", "f21"), ("1", "1"), ("f23", "1"), ("1", "f24"), ("1", "f25"), ("f26", "1"), ("1", "f27"), ("f28", "f22"), ("f29", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "sigmoid(x) = 1/(1+exp(-x))",
    },
    MacroDefinition {
        shorthand_id: "SIM",
        function_class: FunctionClass::NumericalMethod,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a", "b", "fa", "fb", "fmid", "sixth"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "1"), ("f4", "1"), ("1", "f5"), ("1", "fmid"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "fmid"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "f22"), ("f23", "1"), ("1", "f24"), ("f19", "1"), ("f25", "f26"), ("1", "fa"), ("f28", "1"), ("1", "f29"), ("f27", "1"), ("f30", "f31"), ("1", "1"), ("f33", "1"), ("1", "f34"), ("1", "f35"), ("f36", "1"), ("1", "f37"), ("fb", "1"), ("f38", "f39"), ("1", "f32"), ("f41", "1"), ("1", "f42"), ("f40", "1"), ("f43", "f44"), ("1", "1"), ("f46", "1"), ("1", "f47"), ("1", "sixth"), ("f49", "1"), ("1", "f50"), ("1", "f45"), ("f52", "1"), ("1", "f53"), ("1", "f48"), ("f55", "1"), ("1", "f56"), ("f57", "f45"), ("1", "f51"), ("f59", "1"), ("1", "f60"), ("f58", "1"), ("f61", "f62"), ("f63", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Simpson quadrature fragment",
    },
    MacroDefinition {
        shorthand_id: "SIN",
        function_class: FunctionClass::Trigonometric,
        variant_tag: VariantTag::SenderPreprocessed,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "x"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "x"), ("f23", "1"), ("1", "f24"), ("1", "f19"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "f19"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "f38"), ("f42", "1"), ("1", "f43"), ("1", "f19"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "f19"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "f57"), ("f61", "1"), ("1", "f62"), ("1", "f19"), ("f64", "1"), ("1", "f65"), ("1", "f60"), ("f67", "1"), ("1", "f68"), ("f69", "f19"), ("1", "f63"), ("f71", "1"), ("1", "f72"), ("f70", "1"), ("f73", "f74"), ("f75", "1"), ("1", "1"), ("f77", "1"), ("1", "f78"), ("1", "f76"), ("f80", "1"), ("1", "f81"), ("1", "f19"), ("f83", "1"), ("1", "f84"), ("1", "f79"), ("f86", "1"), ("1", "f87"), ("f88", "f19"), ("1", "f82"), ("f90", "1"), ("1", "f91"), ("f89", "1"), ("f92", "f93"), ("f94", "1"), ("1", "1"), ("f96", "1"), ("1", "f97"), ("1", "f95"), ("f99", "1"), ("1", "f100"), ("1", "f19"), ("f102", "1"), ("1", "f103"), ("1", "f98"), ("f105", "1"), ("1", "f106"), ("f107", "f19"), ("1", "f101"), ("f109", "1"), ("1", "f110"), ("f108", "1"), ("f111", "f112"), ("f113", "1"), ("1", "1"), ("f115", "1"), ("1", "f116"), ("1", "f114"), ("f118", "1"), ("1", "f119"), ("1", "f19"), ("f121", "1"), ("1", "f122"), ("1", "f117"), ("f124", "1"), ("1", "f125"), ("f126", "f19"), ("1", "f120"), ("f128", "1"), ("1", "f129"), ("f127", "1"), ("f130", "f131"), ("f132", "1"), ("1", "x"), ("f134", "1"), ("1", "f135"), ("1", "f136"), ("f137", "1"), ("1", "f138"), ("f139", "1"), ("f140", "1"), ("1", "1"), ("f142", "1"), ("1", "f143"), ("1", "f141"), ("f145", "1"), ("1", "f146"), ("1", "1"), ("f148", "1"), ("1", "f149"), ("1", "f144"), ("f151", "1"), ("1", "f152"), ("f153", "1"), ("1", "f147"), ("f155", "1"), ("1", "f156"), ("f154", "1"), ("f157", "f158"), ("f159", "1"), ("1", "1"), ("f161", "1"), ("1", "f162"), ("1", "f163"), ("f164", "1"), ("1", "f165"), ("f160", "1"), ("f166", "f167"), ("1", "1"), ("f169", "1"), ("1", "f170"), ("f168", "1"), ("f171", "f172"), ("1", "f38"), ("f174", "1"), ("1", "f175"), ("1", "f176"), ("f177", "1"), ("1", "f178"), ("f179", "1"), ("f180", "1"), ("1", "1"), ("f182", "1"), ("1", "f183"), ("1", "f181"), ("f185", "1"), ("1", "f186"), ("1", "1"), ("f188", "1"), ("1", "f189"), ("1", "f184"), ("f191", "1"), ("1", "f192"), ("f193", "1"), ("1", "f187"), ("f195", "1"), ("1", "f196"), ("f194", "1"), ("f197", "f198"), ("f199", "1"), ("1", "1"), ("f201", "1"), ("1", "f202"), ("1", "f203"), ("f204", "1"), ("1", "f205"), ("f200", "1"), ("f206", "f207"), ("1", "f173"), ("f209", "1"), ("1", "f210"), ("f208", "1"), ("f211", "f212"), ("1", "f57"), ("f214", "1"), ("1", "f215"), ("1", "f216"), ("f217", "1"), ("1", "f218"), ("f219", "1"), ("f220", "1"), ("1", "1"), ("f222", "1"), ("1", "f223"), ("1", "f221"), ("f225", "1"), ("1", "f226"), ("1", "1"), ("f228", "1"), ("1", "f229"), ("1", "f224"), ("f231", "1"), ("1", "f232"), ("f233", "1"), ("1", "f227"), ("f235", "1"), ("1", "f236"), ("f234", "1"), ("f237", "f238"), ("f239", "1"), ("1", "1"), ("f241", "1"), ("1", "f242"), ("1", "f243"), ("f244", "1"), ("1", "f245"), ("f240", "1"), ("f246", "f247"), ("1", "f213"), ("f249", "1"), ("1", "f250"), ("f248", "1"), ("f251", "f252"), ("1", "f76"), ("f254", "1"), ("1", "f255"), ("1", "f256"), ("f257", "1"), ("1", "f258"), ("f259", "1"), ("f260", "1"), ("1", "1"), ("f262", "1"), ("1", "f263"), ("1", "f261"), ("f265", "1"), ("1", "f266"), ("1", "1"), ("f268", "1"), ("1", "f269"), ("1", "f264"), ("f271", "1"), ("1", "f272"), ("f273", "1"), ("1", "f267"), ("f275", "1"), ("1", "f276"), ("f274", "1"), ("f277", "f278"), ("f279", "1"), ("1", "1"), ("f281", "1"), ("1", "f282"), ("1", "f283"), ("f284", "1"), ("1", "f285"), ("f280", "1"), ("f286", "f287"), ("1", "f253"), ("f289", "1"), ("1", "f290"), ("f288", "1"), ("f291", "f292"), ("1", "f95"), ("f294", "1"), ("1", "f295"), ("1", "f296"), ("f297", "1"), ("1", "f298"), ("f299", "1"), ("f300", "1"), ("1", "1"), ("f302", "1"), ("1", "f303"), ("1", "f301"), ("f305", "1"), ("1", "f306"), ("1", "1"), ("f308", "1"), ("1", "f309"), ("1", "f304"), ("f311", "1"), ("1", "f312"), ("f313", "1"), ("1", "f307"), ("f315", "1"), ("1", "f316"), ("f314", "1"), ("f317", "f318"), ("f319", "1"), ("1", "1"), ("f321", "1"), ("1", "f322"), ("1", "f323"), ("f324", "1"), ("1", "f325"), ("f320", "1"), ("f326", "f327"), ("1", "f293"), ("f329", "1"), ("1", "f330"), ("f328", "1"), ("f331", "f332"), ("1", "f114"), ("f334", "1"), ("1", "f335"), ("1", "f336"), ("f337", "1"), ("1", "f338"), ("f339", "1"), ("f340", "1"), ("1", "1"), ("f342", "1"), ("1", "f343"), ("1", "f341"), ("f345", "1"), ("1", "f346"), ("1", "1"), ("f348", "1"), ("1", "f349"), ("1", "f344"), ("f351", "1"), ("1", "f352"), ("f353", "1"), ("1", "f347"), ("f355", "1"), ("1", "f356"), ("f354", "1"), ("f357", "f358"), ("f359", "1"), ("1", "1"), ("f361", "1"), ("1", "f362"), ("1", "f363"), ("f364", "1"), ("1", "f365"), ("f360", "1"), ("f366", "f367"), ("1", "f333"), ("f369", "1"), ("1", "f370"), ("f368", "1"), ("f371", "f372"), ("1", "f133"), ("f374", "1"), ("1", "f375"), ("1", "f376"), ("f377", "1"), ("1", "f378"), ("f379", "1"), ("f380", "1"), ("1", "1"), ("f382", "1"), ("1", "f383"), ("1", "f381"), ("f385", "1"), ("1", "f386"), ("1", "1"), ("f388", "1"), ("1", "f389"), ("1", "f384"), ("f391", "1"), ("1", "f392"), ("f393", "1"), ("1", "f387"), ("f395", "1"), ("1", "f396"), ("f394", "1"), ("f397", "f398"), ("f399", "1"), ("1", "1"), ("f401", "1"), ("1", "f402"), ("1", "f403"), ("f404", "1"), ("1", "f405"), ("f400", "1"), ("f406", "f407"), ("1", "f373"), ("f409", "1"), ("1", "f410"), ("f408", "1"), ("f411", "f412")],
        },
    ],
        preprocessing: Some("modulo_2pi_with_quadrant"),
        postprocessing: Some("apply_quadrant_sign_for_sin"),
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "sin(x) Taylor (principal-domain)",
    },
    MacroDefinition {
        shorthand_id: "SNH",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "half"],
            levels: &[("x", "1"), ("1", "1"), ("f2", "1"), ("1", "f3"), ("1", "f4"), ("f5", "1"), ("1", "f6"), ("x", "1"), ("f7", "f8"), ("f9", "1"), ("1", "f1"), ("f11", "1"), ("1", "f12"), ("f10", "1"), ("f13", "f14"), ("1", "1"), ("f16", "1"), ("1", "f17"), ("1", "f15"), ("f19", "1"), ("1", "f20"), ("1", "half"), ("f22", "1"), ("1", "f23"), ("1", "f18"), ("f25", "1"), ("1", "f26"), ("f27", "half"), ("1", "f21"), ("f29", "1"), ("1", "f30"), ("f28", "1"), ("f31", "f32"), ("f33", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "sinh(x)",
    },
    MacroDefinition {
        shorthand_id: "SPL",
        function_class: FunctionClass::NnActivation,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("x", "1"), ("1", "1"), ("f2", "1"), ("1", "f3"), ("1", "f4"), ("f5", "1"), ("1", "f6"), ("f1", "1"), ("f7", "f8"), ("1", "1"), ("f10", "1"), ("1", "f11"), ("f9", "1"), ("f12", "f13"), ("1", "f14"), ("f15", "1"), ("1", "f16")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "softplus(x) = ln(1+exp(x))",
    },
    MacroDefinition {
        shorthand_id: "SQR",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "x"), ("f4", "1"), ("1", "f5"), ("1", "x"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "x"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "x^2",
    },
    MacroDefinition {
        shorthand_id: "SQT",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "half"],
            levels: &[("1", "x"), ("f1", "1"), ("1", "f2"), ("1", "1"), ("f4", "1"), ("1", "f5"), ("1", "half"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("1", "f6"), ("f13", "1"), ("1", "f14"), ("f15", "f3"), ("1", "f9"), ("f17", "1"), ("1", "f18"), ("f16", "1"), ("f19", "f20"), ("f21", "1"), ("f22", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "sqrt(x) = x^0.5 (sender provides half=0.5)",
    },
    MacroDefinition {
        shorthand_id: "STB",
        function_class: FunctionClass::Scientific,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["T", "R", "sigma", "four_pi"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "T"), ("f4", "1"), ("1", "f5"), ("1", "T"), ("f7", "1"), ("1", "f8"), ("1", "f3"), ("f10", "1"), ("1", "f11"), ("f12", "T"), ("1", "f6"), ("f14", "1"), ("1", "f15"), ("f13", "1"), ("f16", "f17"), ("f18", "1"), ("1", "1"), ("f20", "1"), ("1", "f21"), ("1", "f19"), ("f23", "1"), ("1", "f24"), ("1", "f19"), ("f26", "1"), ("1", "f27"), ("1", "f22"), ("f29", "1"), ("1", "f30"), ("f31", "f19"), ("1", "f25"), ("f33", "1"), ("1", "f34"), ("f32", "1"), ("f35", "f36"), ("f37", "1"), ("1", "1"), ("f39", "1"), ("1", "f40"), ("1", "R"), ("f42", "1"), ("1", "f43"), ("1", "R"), ("f45", "1"), ("1", "f46"), ("1", "f41"), ("f48", "1"), ("1", "f49"), ("f50", "R"), ("1", "f44"), ("f52", "1"), ("1", "f53"), ("f51", "1"), ("f54", "f55"), ("f56", "1"), ("1", "1"), ("f58", "1"), ("1", "f59"), ("1", "four_pi"), ("f61", "1"), ("1", "f62"), ("1", "f57"), ("f64", "1"), ("1", "f65"), ("1", "f60"), ("f67", "1"), ("1", "f68"), ("f69", "f57"), ("1", "f63"), ("f71", "1"), ("1", "f72"), ("f70", "1"), ("f73", "f74"), ("f75", "1"), ("1", "1"), ("f77", "1"), ("1", "f78"), ("1", "f76"), ("f80", "1"), ("1", "f81"), ("1", "sigma"), ("f83", "1"), ("1", "f84"), ("1", "f79"), ("f86", "1"), ("1", "f87"), ("f88", "sigma"), ("1", "f82"), ("f90", "1"), ("1", "f91"), ("f89", "1"), ("f92", "f93"), ("f94", "1"), ("1", "1"), ("f96", "1"), ("1", "f97"), ("1", "f95"), ("f99", "1"), ("1", "f100"), ("1", "f38"), ("f102", "1"), ("1", "f103"), ("1", "f98"), ("f105", "1"), ("1", "f106"), ("f107", "f38"), ("1", "f101"), ("f109", "1"), ("1", "f110"), ("f108", "1"), ("f111", "f112"), ("f113", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Stefan-Boltzmann scaled L/L_sun",
    },
    MacroDefinition {
        shorthand_id: "SUB",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x", "y"],
            levels: &[("1", "x"), ("f1", "1"), ("1", "f2"), ("y", "1"), ("f3", "f4")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "x - y",
    },
    MacroDefinition {
        shorthand_id: "SWS",
        function_class: FunctionClass::NnActivation,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("x", "1"), ("f6", "f7"), ("f8", "1"), ("1", "1"), ("f10", "1"), ("1", "f11"), ("1", "f12"), ("f13", "1"), ("1", "f14"), ("f9", "1"), ("f15", "f16"), ("1", "1"), ("f18", "1"), ("1", "f19"), ("f17", "1"), ("f20", "f21"), ("1", "1"), ("f23", "1"), ("1", "f24"), ("1", "f25"), ("f26", "1"), ("1", "f27"), ("f28", "f22"), ("f29", "1"), ("1", "1"), ("f31", "1"), ("1", "f32"), ("1", "x"), ("f34", "1"), ("1", "f35"), ("1", "f30"), ("f37", "1"), ("1", "f38"), ("1", "f33"), ("f40", "1"), ("1", "f41"), ("f42", "f30"), ("1", "f36"), ("f44", "1"), ("1", "f45"), ("f43", "1"), ("f46", "f47"), ("f48", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "Swish/SiLU = x * sigmoid(x)",
    },
    MacroDefinition {
        shorthand_id: "SX3",
        function_class: FunctionClass::NnActivation,
        variant_tag: VariantTag::MultiOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x1", "x2", "x3"],
            levels: &[("x1", "1"), ("x2", "1"), ("x3", "1"), ("1", "1"), ("f4", "1"), ("1", "f5"), ("1", "f6"), ("f7", "1"), ("1", "f8"), ("f2", "1"), ("f9", "f10"), ("1", "f1"), ("f12", "1"), ("1", "f13"), ("f11", "1"), ("f14", "f15"), ("1", "1"), ("f17", "1"), ("1", "f18"), ("1", "f19"), ("f20", "1"), ("1", "f21"), ("f3", "1"), ("f22", "f23"), ("1", "f16"), ("f25", "1"), ("1", "f26"), ("f24", "1"), ("f27", "f28"), ("1", "f1"), ("f30", "1"), ("1", "f31"), ("1", "f32"), ("f33", "1"), ("1", "f34"), ("f35", "f29"), ("f36", "1")],
        },
        ParametricChain {
            variables: &["x1", "x2", "x3"],
            levels: &[("x1", "1"), ("x2", "1"), ("x3", "1"), ("1", "1"), ("f4", "1"), ("1", "f5"), ("1", "f6"), ("f7", "1"), ("1", "f8"), ("f2", "1"), ("f9", "f10"), ("1", "f1"), ("f12", "1"), ("1", "f13"), ("f11", "1"), ("f14", "f15"), ("1", "1"), ("f17", "1"), ("1", "f18"), ("1", "f19"), ("f20", "1"), ("1", "f21"), ("f3", "1"), ("f22", "f23"), ("1", "f16"), ("f25", "1"), ("1", "f26"), ("f24", "1"), ("f27", "f28"), ("1", "f1"), ("f30", "1"), ("1", "f31"), ("1", "f32"), ("f33", "1"), ("1", "f34"), ("f35", "f29"), ("f36", "1"), ("1", "f2"), ("f38", "1"), ("1", "f39"), ("1", "f40"), ("f41", "1"), ("1", "f42"), ("f43", "f29"), ("f44", "1")],
        },
        ParametricChain {
            variables: &["x1", "x2", "x3"],
            levels: &[("x1", "1"), ("x2", "1"), ("x3", "1"), ("1", "1"), ("f4", "1"), ("1", "f5"), ("1", "f6"), ("f7", "1"), ("1", "f8"), ("f2", "1"), ("f9", "f10"), ("1", "f1"), ("f12", "1"), ("1", "f13"), ("f11", "1"), ("f14", "f15"), ("1", "1"), ("f17", "1"), ("1", "f18"), ("1", "f19"), ("f20", "1"), ("1", "f21"), ("f3", "1"), ("f22", "f23"), ("1", "f16"), ("f25", "1"), ("1", "f26"), ("f24", "1"), ("f27", "f28"), ("1", "f1"), ("f30", "1"), ("1", "f31"), ("1", "f32"), ("f33", "1"), ("1", "f34"), ("f35", "f29"), ("f36", "1"), ("1", "f2"), ("f38", "1"), ("1", "f39"), ("1", "f40"), ("f41", "1"), ("1", "f42"), ("f43", "f29"), ("f44", "1"), ("1", "f3"), ("f46", "1"), ("1", "f47"), ("1", "f48"), ("f49", "1"), ("1", "f50"), ("f51", "f29"), ("f52", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "softmax3 (3-class)",
    },
    MacroDefinition {
        shorthand_id: "TNH",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("x", "1"), ("1", "1"), ("f2", "1"), ("1", "f3"), ("1", "f4"), ("f5", "1"), ("1", "f6"), ("x", "1"), ("f7", "f8"), ("f9", "1"), ("1", "f1"), ("f11", "1"), ("1", "f12"), ("f10", "1"), ("f13", "f14"), ("1", "1"), ("f16", "1"), ("1", "f17"), ("1", "f18"), ("f19", "1"), ("1", "f20"), ("f10", "1"), ("f21", "f22"), ("1", "f1"), ("f24", "1"), ("1", "f25"), ("f23", "1"), ("f26", "f27"), ("1", "f15"), ("f29", "1"), ("1", "f30"), ("1", "f31"), ("f32", "1"), ("1", "f33"), ("f34", "f28"), ("f35", "1")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "tanh(x)",
    },
    MacroDefinition {
        shorthand_id: "TR3",
        function_class: FunctionClass::LinAlg,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["a11", "a22", "a33"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2"), ("1", "f3"), ("f4", "1"), ("1", "f5"), ("a22", "1"), ("f6", "f7"), ("1", "a11"), ("f9", "1"), ("1", "f10"), ("f8", "1"), ("f11", "f12"), ("1", "1"), ("f14", "1"), ("1", "f15"), ("1", "f16"), ("f17", "1"), ("1", "f18"), ("a33", "1"), ("f19", "f20"), ("1", "f13"), ("f22", "1"), ("1", "f23"), ("f21", "1"), ("f24", "f25")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "trace of 3x3 matrix",
    },
    MacroDefinition {
        shorthand_id: "ZER",
        function_class: FunctionClass::CompoundArithmetic,
        variant_tag: VariantTag::SingleOutput,
        chain_templates: &[
        ParametricChain {
            variables: &["x"],
            levels: &[("1", "1"), ("f1", "1"), ("1", "f2")],
        },
    ],
        preprocessing: None,
        postprocessing: None,
        precision_class: PrecisionClass::Faithful1Ulp,
        envelope_bound: None,
        patent_claim_refs: &[],
        fingerprint_membership: FingerprintMembership::InBitExactCorpus,
        description: "zero (x-independent)",
    },
];

/// Returns the number of registered macros (89).
pub fn macro_count() -> usize {
    REGISTRY.len()
}

/// Iterator over macros that participate in the bit-exact cross-SDK corpus.
pub fn in_bit_exact_corpus() -> impl Iterator<Item = &'static MacroDefinition> {
    REGISTRY
        .iter()
        .filter(|m| m.fingerprint_membership == FingerprintMembership::InBitExactCorpus)
}

/// Looks up a macro by its 1-6 character shorthand identifier.
pub fn lookup(shorthand_id: &str) -> Option<&'static MacroDefinition> {
    REGISTRY.iter().find(|m| m.shorthand_id == shorthand_id)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn registry_has_89_macros() {
        assert_eq!(macro_count(), 89);
    }

    #[test]
    fn lookup_exp() {
        let m = lookup("EXP").expect("EXP must be present");
        assert_eq!(m.shorthand_id, "EXP");
        assert_eq!(m.function_class, FunctionClass::CompoundArithmetic);
        assert_eq!(m.variant_tag, VariantTag::SingleOutput);
        assert_eq!(m.chain_templates.len(), 1);
        assert_eq!(m.chain_templates[0].variables, &["x"]);
        assert_eq!(m.chain_templates[0].levels, &[("x", "1")]);
    }

    #[test]
    fn lookup_unknown_returns_none() {
        assert!(lookup("DOES_NOT_EXIST").is_none());
    }

    #[test]
    fn in_bit_exact_corpus_subset() {
        let in_corpus = in_bit_exact_corpus().count();
        // The bit-exact corpus is a strict subset of the full registry.
        assert!(in_corpus > 0);
        assert!(in_corpus <= macro_count());
    }

    #[test]
    fn shorthand_ids_unique() {
        let mut seen: Vec<&str> = REGISTRY.iter().map(|m| m.shorthand_id).collect();
        seen.sort_unstable();
        let n = seen.len();
        seen.dedup();
        assert_eq!(seen.len(), n, "duplicate shorthand_id detected");
    }
}
