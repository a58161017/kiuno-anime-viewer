## ADDED Requirements

### Requirement: 主清單同步

網站資料庫（`data/anime.json`）SHALL 涵蓋 owner 主清單（Google Doc）上所有已觀看或觀看中的條目；`raw/anime_list.txt` SHALL 作為主清單的本地鏡像，同步時以 Doc 內容為準更新。「待追」（尚未開始看）區段的條目不在收錄範圍。

#### Scenario: 主清單新增條目後同步

- **WHEN** 主清單新增了網站上沒有的已觀看/觀看中條目，並執行一次同步
- **THEN** 該條目出現在 `data/anime.json`（含 metadata、封面、graph 連結），且 `raw/anime_list.txt` 已反映主清單內容

#### Scenario: 待追條目不納入

- **WHEN** 主清單「待追」區段含有網站上沒有的條目
- **THEN** 同步後該條目不出現在 `data/anime.json`
