import streamlit as st
from PIL import Image
import io
import zipfile

# --- ページ設定 ---
st.set_page_config(page_title="一括リネームツール", layout="wide")
st.title("🏷️ 画像一括リネームツール (手動設定版)")

# --- セッション状態の初期化 ---
# 画像データと編集後の名前を保持する
if 'results' not in st.session_state:
    st.session_state.results = {} # {index: data}

# --- Zip作成関数 ---
def create_zip(results_dict):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        # index順に格納
        for idx in sorted(results_dict.keys()):
            item = results_dict[idx]
            fname = f"{item['current_name']}.{item['ext']}"
            
            # 画像データをバイト列に
            img_byte_arr = io.BytesIO()
            item['image'].save(img_byte_arr, format=item['save_format'])
            zf.writestr(fname, img_byte_arr.getvalue())
    return zip_buffer.getvalue()

# --- コールバック: 名前変更を保存 ---
def update_name(index):
    new_val = st.session_state[f"input_{index}"]
    st.session_state.results[index]['current_name'] = new_val

# --- 行描画関数 ---
def render_row(index, item):
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            st.image(item['image'], width=150)
        with col2:
            st.text_input(
                "ファイル名",
                value=item['current_name'],
                key=f"input_{index}",
                on_change=update_name,
                args=(index,)
            )
            st.caption(f"元ファイル: {item['original_name']}")
        with col3:
            final_fname = f"{item['current_name']}.{item['ext']}"
            img_byte_arr = io.BytesIO()
            item['image'].save(img_byte_arr, format=item['save_format'])
            
            st.write("") # レイアウト調整
            st.download_button(
                "⬇️ 保存",
                data=img_byte_arr.getvalue(),
                file_name=final_fname,
                mime=item['mime'],
                key=f"dl_{index}"
            )
    st.divider()

# --- UI構築 ---

with st.sidebar:
    st.header("共通設定")
    
    # 1. ジャンル
    selected_genre = st.selectbox(
        "① ジャンル",
        ["ダイエット", "育毛・ヘアケア", "美容", "健康", "その他"],
        index=0
    )
    
    # 2. 年代 (仕様変更①)
    selected_age = st.selectbox(
        "② 年代",
        ["若年", "中年", "高齢"],
        index=1
    )
    
    # 3. 属性テキスト (仕様変更③)
    input_attr = st.text_input(
        "③ 属性 (テキスト入力)",
        value="女性_笑顔",
        placeholder="例: 男性_悩み"
    )
    
    # 4. 開始No (仕様変更②)
    start_no = st.number_input(
        "④ 開始No",
        min_value=1,
        value=1,
        step=1,
        help="ここに入力した数字から連番が始まります"
    )

    st.markdown("---")
    if st.button("リセット / 最初から"):
        st.session_state.results = {}
        st.rerun()

st.write("##### 画像アップロード")
uploaded_files = st.file_uploader(
    "画像をアップロードしてください", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

top_zip_area = st.empty()

# --- メインエリア (常に表示) ---
if st.session_state.results:
    for i in sorted(st.session_state.results.keys()):
        render_row(i, st.session_state.results[i])

# --- リネーム実行処理 ---
if uploaded_files:
    # 未処理のファイルがあるかチェック
    processed_ids = st.session_state.results.keys()
    unprocessed_indices = [i for i in range(len(uploaded_files)) if i not in processed_ids]
    
    if unprocessed_indices:
        btn_label = "一括リネーム実行"
    else:
        btn_label = "リネーム実行 (完了済み)"

    if st.button(btn_label, type="primary"):
        if unprocessed_indices:
            # プログレスバー（AIがないので一瞬ですが、枚数が多い時のために設置）
            progress_bar = st.progress(0)
            
            for idx, i in enumerate(unprocessed_indices):
                uploaded_file = uploaded_files[i]
                try:
                    image = Image.open(uploaded_file).convert('RGB')
                    
                    # --- 命名ロジック ---
                    # 連番の計算: 開始No + (現在のループ位置)
                    # 全体の中での通し番号にするため、unprocessedリスト内の順序を加算
                    current_no = start_no + idx
                    
                    # 属性テキストが空の場合はアンダーバーが重ならないように調整
                    attr_part = f"_{input_attr}" if input_attr else ""
                    
                    # フォーマット: ジャンル_年代_属性_No
                    # Noは2桁埋め (01, 02...) にしておくと並び順が綺麗です
                    # 不要なら `{current_no}` に変更してください
                    base_name = f"{selected_genre}_{selected_age}{attr_part}_{current_no:02}"
                    
                    # 拡張子処理
                    original_ext = uploaded_file.name.split('.')[-1].lower()
                    if original_ext == 'jpeg': original_ext = 'jpg'
                    save_format = 'PNG' if original_ext == 'png' else 'JPEG'
                    mime = "image/png" if original_ext == 'png' else "image/jpeg"

                    # データ保存
                    item_data = {
                        "image": image,
                        "original_name": uploaded_file.name,
                        "current_name": base_name,
                        "ext": original_ext,
                        "save_format": save_format,
                        "mime": mime
                    }
                    st.session_state.results[i] = item_data
                    
                    # 即時表示
                    render_row(i, item_data)

                except Exception as e:
                    st.error(f"{uploaded_file.name} でエラー: {e}")
                
                progress_bar.progress((idx + 1) / len(unprocessed_indices))
            
            st.success("完了しました！")

# --- Zipボタン ---
if st.session_state.results:
    zip_data = create_zip(st.session_state.results)
    
    top_zip_area.download_button(
        "📦 Zipダウンロード (上)",
        data=zip_data,
        file_name="renamed_images.zip",
        mime="application/zip",
        key="zip_top"
    )
    
    st.download_button(
        "📦 Zipダウンロード (下)",
        data=zip_data,
        file_name="renamed_images.zip",
        mime="application/zip",
        key="zip_bottom"
    )
