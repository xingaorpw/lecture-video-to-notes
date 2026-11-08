from pptx_build import sanitize_formula


def test_infty_is_not_mangled_into_mathrm_infty():
    assert sanitize_formula(r"$$+\infty$$") == r"+\infty"


def test_ge_le_aliases():
    assert sanitize_formula(r"$$a \ge b$$") == r"a \geq b"
    assert sanitize_formula(r"$$a \le b$$") == r"a \leq b"
    assert sanitize_formula(r"$$a \geq b$$") == r"a \geq b"


def test_int_and_frac_aliases():
    assert sanitize_formula(r"$$\iint f$$") == r"\int\int f"
    assert sanitize_formula(r"$$\dfrac{1}{2}$$") == r"\frac{1}{2}"
