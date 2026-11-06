"""uvx --python 3.12 --with pytest pytest -q scripts/test_match.py"""

from match import lot, match, muni, norm


def test_norm_folds_width_and_drops_spaces():
    assert norm(" 大興寺 下池　") == "大興寺下池"
    assert norm("ﾊﾘﾉｷ池") == "ハリノキ池"


def test_muni_drops_the_county():
    assert muni("仲多度郡まんのう町") == "まんのう町"
    assert muni("綾歌郡 綾川町") == "綾川町"
    assert muni("福山市") == "福山市"


def test_lot_is_the_first_run_of_digits():
    assert lot("綾歌郡 綾川町山田上甲1393") == "1393"
    assert lot("綾川町山田上１３９３番地2") == "1393"
    assert lot("安芸区畑賀一丁目241番") == "241"
    assert lot("字池尻") == ""


L = [dict(source_row=1, municipality="綾歌郡綾川町", name="新池", address="綾川町東分1254"),
     dict(source_row=2, municipality="綾歌郡綾川町", name="新池", address="綾川町西分3050"),
     dict(source_row=3, municipality="綾歌郡綾川町", name="大興寺下池", address="綾川町山田上1393"),
     dict(source_row=4, municipality="綾歌郡綾川町", name="西山池", address="綾川町羽床下字平芝1799"),
     dict(source_row=5, municipality="綾歌郡綾川町", name="西山池", address="綾川町滝宮字中原1837")]


def test_match_by_name_and_lot_then_by_unique_name():
    lists = [dict(municipality="綾川町", name="新池", address="綾歌郡 綾川町東分1254"),          # key 1
             dict(municipality="綾川町", name="大興寺下池", address="綾歌郡 綾川町山田上甲9999"),  # lot differs, name unique
             dict(municipality="綾川町", name="西山池", address="綾歌郡 綾川町滝宮"),            # no lot, name not unique
             dict(municipality="綾川町", name="無い池", address="綾川町1")]
    got = match(lists, L)
    assert got == [(1, "key1"), (3, "key2"), (None, "none"), (None, "none")]


def test_key1_with_two_ledger_rows_falls_back_to_the_whole_address():
    dup = L + [dict(source_row=6, municipality="綾歌郡綾川町", name="新池", address="綾川町東分1254-2")]
    # the lot 1254 gives two rows and the name is shared, so keys 1 and 2 fail; the whole address picks row 1
    assert match([dict(municipality="綾川町", name="新池", address="東分1254")], dup) == [((1,), "key4")]
    assert match([dict(municipality="綾川町", name="新池", address="東分")], dup) == [(None, "none")]


def test_loose_mode_takes_every_row_with_the_name():
    got = match([dict(municipality="綾川町", name="西山池", address="")], L, loose=True)
    assert got == [((4, 5), "loose")]


def test_key3_uses_lot_height_and_storage_when_the_name_is_missing():
    led = L + [dict(source_row=7, municipality="福山市", name="般若池", address="駅家町2547", dam_height_m=6.0,
                    storage_thousand_m3=12.33),
               dict(source_row=8, municipality="福山市", name="上池", address="駅家町2547", dam_height_m=3.0,
                    storage_thousand_m3=1.0)]
    lists = [dict(municipality="福山市", name="", address="駅家町２５４７", dam_height_m="6.0", storage_thousand_m3="12.33"),
             dict(municipality="福山市", name="", address="駅家町２５４７", dam_height_m="", storage_thousand_m3="")]
    assert match(lists, led) == [(7, "key3"), (None, "none")]


def test_key4_takes_every_ledger_row_with_the_same_name_and_address():
    led = [dict(source_row=10, municipality="淡路市", name="新池", address="池ノ内"),
           dict(source_row=11, municipality="淡路市", name="新池", address="大谷"),
           dict(source_row=12, municipality="淡路市", name="新池", address="大谷"),
           dict(source_row=13, municipality="洲本市", name="阿僧谷池", address="洲本市五色町鮎原葛尾474"),
           dict(source_row=14, municipality="洲本市", name="阿僧谷池", address="五色町鮎原葛尾474")]
    lists = [dict(municipality="淡路市", name="新池", address="池ノ内"),
             dict(municipality="淡路市", name="新池", address="大谷"),
             dict(municipality="淡路市", name="新池", address="佐野"),
             dict(municipality="洲本市", name="阿僧谷池", address="五色町鮎原葛尾474")]
    assert match(lists, led) == [((10,), "key4"), ((11, 12), "key4"), (None, "none"), ((13, 14), "key4")]
