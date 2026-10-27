"""Patient codes: format, check character, and detection of the copying mistakes it is meant to catch."""
import itertools

from app.core import patient_codes as pc


def test_generated_codes_have_the_expected_format_and_pass_validation():
    codes = [pc.generate() for _ in range(500)]
    assert all(pc.PATTERN.match(code) and pc.is_valid(code) for code in codes)
    assert len(set(codes)) > 490  # random, not sequential


def test_validation_ignores_case_and_surrounding_spaces():
    code = pc.generate()
    assert pc.is_valid(f"  {code.lower()} ")


def test_every_single_wrong_character_is_detected():
    code = pc.generate()
    for position in range(len(pc.PREFIX), len(code)):
        for replacement in pc.ALPHABET:
            if replacement != code[position]:
                typo = code[:position] + replacement + code[position + 1:]
                assert not pc.is_valid(typo), typo


def test_swapping_two_neighbouring_characters_is_detected_in_almost_all_cases():
    swaps = detected = 0
    for _ in range(300):
        code = pc.generate()
        for i in range(len(pc.PREFIX), len(code) - 1):
            if code[i] != code[i + 1]:
                swaps += 1
                detected += not pc.is_valid(code[:i] + code[i + 1] + code[i] + code[i + 2:])
    assert detected / swaps > 0.95


def test_confusable_characters_are_not_used_and_alphabet_size_is_even():
    assert not set("01ILOU") & set(pc.ALPHABET)
    assert len(pc.ALPHABET) % 2 == 0  # Luhn mod N needs doubling to be one-to-one


def test_malformed_codes_are_rejected():
    for bad in ("", "PHC-", "PHC-12345", "Jane Doe", "PHC-ABCDE0", "XYZ-ABCDEF", "PHC-ABCDEFG"):
        assert not pc.is_valid(bad), bad


def test_known_values_match_the_browser_implementation():
    # The same three values are pinned in frontend/src/lib/patientCode.test.ts.
    assert (pc.check_character("7K3Q9"), pc.check_character("22222"), pc.check_character("ZZZZZ")) == ("W", "2", "7")
    assert all(pc.is_valid(f"PHC-{body}{pc.check_character(body)}")
               for body in ("".join(p) for p in itertools.islice(itertools.product("29AZ", repeat=5), 200)))
