import streamlit as st
from PIL import Image
import io
import zipfile

# --- ページ設定 ---
st.set_page_config(page_title="一括リネームツール", layout="wide")
st.title("🏷️ 画像一括リネームツール (ルールベース)")

# --- セッション状態の初期化 ---
if 'results' not in st.session_state:
    st.session_state.results = {} # {index: data}

# --- Zip作成関数 ---
def create_zip(results_dict):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for idx in sorted(results_dict.keys()):
            item = results_dict[idx]
            fname = f"{item['current_name']}.{item['ext']}"
            img_byte_arr = io.BytesIO()
            item['image'].save(img_byte_arr, format=item['save_format'])
            zf.writestr(fname, img_byte_arr.getvalue())
    return zip_buffer.getvalue()

# --- コールバック: 名前変更を即座に保存 ---
def update_name(index):
    new_val = st.session_state[f"input_{index}"]
    st.session_state.results[index]['current_name'] = new_val

# --- 表示用の関数 ---
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
            st.caption(f"元ファイル名: {item['original_name']}")
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
    st.header("命名ルール設定")
    
    # ① 年代 (選択式)
    setting_age = st.selectbox(
        "年代",
        ["若年", "中年", "高齢"],
        index=0
    )
    
    # ③ 属性 (テキスト入力)
    setting_attr = st.text_input(
        "属性 (例: 笑顔の女性)",
        value="人物"
    )
    
    # ② No (連番設定)
    setting_no = st.text_input(
        "開始No (例: 001)",
        value="001",
        help="ここで入力した桁数に合わせて連番が振られます（001なら001, 002...）"
    )

    st.markdown("---")
    if st.button("リセット / 最初から"):
        st.session_state.results = {}
        st.rerun()

st.write("##### 画像アップロード")
st.caption("設定したルールに基づいて一括で名前を生成します。")

uploaded_files = st.file_uploader(
    "画像を選択", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

top_zip_area = st.empty()

# --- メインエリア (常に表示) ---
if st.session_state.results:
    for i in sorted(st.session_state.results.keys()):
        render_row(i, st.session_state.results[i])

# --- 実行ロジック ---
if uploaded_files:
    # まだ処理していないファイル、または再実行ボタンが押された場合
    
    # 未処理のインデックスを探す
    processed_ids = st.session_state.results.keys()
    unprocessed_indices = [i for i in range(len(uploaded_files)) if i not in processed_ids]
    
    btn_label = "命名ルールを適用して表示"
    
    # 実行ボタン
    if st.button(btn_label, type="primary"):
        
        # 連番の桁数と開始値を計算
        try:
            start_num = int(setting_no)
            padding = len(setting_no) # 入力された桁数 (例: "001"なら3桁)
        except ValueError:
            start_num = 1
            padding = 3

        # プログレスバー（軽いので一瞬ですが一応）
        progress_bar = st.progress(0)
        
        # 全ファイルをループ (未処理のものだけ追加するロジック)
        # ※もし設定を変えて「全画像やり直し」したい場合はリセットボタンを押してもらう運用
        
        target_indices = unprocessed_indices if unprocessed_indices else range(len(uploaded_files))
        
        # すべて再生成する場合の考慮:
        # 既にリストにあっても、ボタンを押したということは「今の設定で上書きしたい」可能性が高いので
        # ここではアップロードされている全ファイルを対象に処理します。
        
        for i, uploaded_file in enumerate(uploaded_files):
            try:
                # 連番生成 (開始値 + インデックス)
                current_num = start_num + i
                num_str = str(current_num).zfill(padding)
                
                # ファイル名生成: 年代_属性_No
                new_base_name = f"{setting_age}_{setting_attr}_{num_str}"
                
                # 画像情報の取得
                image = Image.open(uploaded_file).convert('RGB')
                original_ext = uploaded_file.name.split('.')[-1].lower()
                if original_ext == 'jpeg': original_ext = 'jpg'
                save_format = 'PNG' if original_ext == 'png' else 'JPEG'
                mime = "image/png" if original_ext == 'png' else "image/jpeg"

                # データ作成
                item_data = {
                    "image": image,
                    "original_name": uploaded_file.name,
                    "current_name": new_base_name,
                    "ext": original_ext,
                    "save_format": save_format,
                    "mime": mime,
                    "caption_debug": "Rule Based"
                }
                
                # Session Stateに保存 (上書き)
                st.session_state.results[i] = item_data
                
            except Exception as e:
                st.error(f"{uploaded_file.name} でエラー: {e}")
            
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        st.success("適用完了！")
        st.rerun() # 描画更新のためにリロード

# --- Zipボタン ---
if st.session_state.results:
    zip_data = create_zip(st.session_state.results)
    
    top_zip_area.download_button(
        "📦 Zipダウンロード (上)",
        data=zip_data,
        file_name="images_renamed.zip",
        mime="application/zip",
        key="zip_top"
    )
    
    st.download_button(
        "📦 Zipダウンロード (下)",
        data=zip_data,
        file_name="images_renamed.zip",
        mime="application/zip",
        key="zip_bottom"
    )
