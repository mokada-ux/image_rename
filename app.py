import streamlit as st
from PIL import Image
import io
import zipfile

# --- ページ設定 ---
st.set_page_config(page_title="一括リネームツール", layout="wide")
st.title("🏷️ 画像一括リネームツール (年代_No_状態)")

# --- セッション状態の初期化 ---
if 'results' not in st.session_state:
    st.session_state.results = {} # {original_index: data}

# --- Zip作成関数 ---
def create_zip(results_dict):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        # キー（index）でソートして格納
        for idx in sorted(results_dict.keys()):
            item = results_dict[idx]
            fname = f"{item['current_name']}.{item['ext']}"
            img_byte_arr = io.BytesIO()
            item['image'].save(img_byte_arr, format=item['save_format'])
            zf.writestr(fname, img_byte_arr.getvalue())
    return zip_buffer.getvalue()

# --- コールバック関数 ---

def update_name_manual(index):
    """手動で名前を変更した時に呼ばれる"""
    new_val = st.session_state[f"input_{index}"]
    st.session_state.results[index]['current_name'] = new_val

def delete_image(index):
    """削除ボタンが押された時に呼ばれる"""
    if index in st.session_state.results:
        del st.session_state.results[index]

# --- 表示用関数 (1行描画) ---
def render_row(index, item):
    with st.container():
        # レイアウト: 画像 | 入力欄 | 保存ボタン | 削除ボタン
        col1, col2, col3, col4 = st.columns([1, 2.5, 0.8, 0.5])
        
        with col1:
            st.image(item['image'], width=150)
            
        with col2:
            st.text_input(
                "ファイル名",
                value=item['current_name'],
                key=f"input_{index}",
                on_change=update_name_manual,
                args=(index,)
            )
            st.caption(f"元ファイル: {item['original_name']}")
            
        with col3:
            final_fname = f"{item['current_name']}.{item['ext']}"
            img_byte_arr = io.BytesIO()
            item['image'].save(img_byte_arr, format=item['save_format'])
            st.write("") # 上部の余白調整
            st.download_button(
                "⬇️ 保存",
                data=img_byte_arr.getvalue(),
                file_name=final_fname,
                mime=item['mime'],
                key=f"dl_{index}"
            )
            
        with col4:
            st.write("") # 上部の余白調整
            # 削除ボタン
            st.button(
                "🗑️",
                key=f"del_{index}",
                on_click=delete_image,
                args=(index,),
                help="リストから削除"
            )
    st.divider()

# --- UI構築 ---

with st.sidebar:
    st.header("命名ルール設定")
    
    # ① 年代
    setting_age = st.selectbox("① 年代", ["若年", "中年", "高齢"], index=0)

    # ② No
    setting_no = st.text_input("② 開始No", value="001")
    
    # ③ 状態
    setting_status = st.text_input("③ 状態", value="", placeholder="例: 笑顔")
    
    st.info(f"イメージ: {setting_age}_{setting_no}_{setting_status if setting_status else '状態'}.jpg")

    # --- 更新ボタン (修正箇所) ---
    st.markdown("---")
    st.write("**ルールの再適用**")
    if st.button("🔄 名前を更新・連番振り直し", type="primary", help="現在リストにある画像に対して、上に入力されたルールを適用し直します。"):
        # 連番設定の読み込み
        try:
            start_num = int(setting_no)
            padding = len(setting_no)
        except ValueError:
            start_num = 1
            padding = 3
        
        # 現在残っている画像をソートしてループ
        current_keys = sorted(st.session_state.results.keys())
        
        for i, key in enumerate(current_keys):
            item = st.session_state.results[key]
            
            # 新しい連番
            current_num = start_num + i
            num_str = str(current_num).zfill(padding)
            
            # 新しい名前を生成
            new_base_name = f"{setting_age}_{num_str}_{setting_status}"
            
            # 1. データの更新
            item['current_name'] = new_base_name
            
            # 2. ★ここが修正点★
            # 入力ボックス(Widget)のキャッシュも強制的に書き換える
            # これをしないと画面上の文字が変わらない
            if f"input_{key}" in st.session_state:
                st.session_state[f"input_{key}"] = new_base_name
            
        st.success("更新しました！")
        st.rerun()

    st.markdown("---")
    if st.button("全リセット"):
        st.session_state.results = {}
        st.rerun()

# --- メインエリア ---
st.write("##### 画像アップロード")

uploaded_files = st.file_uploader(
    "画像を選択", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

top_zip_area = st.empty()

# リスト表示 (常に表示)
if st.session_state.results:
    for i in sorted(st.session_state.results.keys()):
        render_row(i, st.session_state.results[i])
else:
    st.info("画像が表示されます")

# --- 新規アップロード時の処理 ---
if uploaded_files:
    existing_ids = st.session_state.results.keys()
    new_indices = [i for i in range(len(uploaded_files)) if i not in existing_ids]
    
    if new_indices:
        if st.button(f"新規画像 {len(new_indices)}枚 を追加・適用"):
            try:
                start_num = int(setting_no)
                padding = len(setting_no)
            except:
                start_num = 1
                padding = 3

            current_count = len(st.session_state.results)
            effective_start_num = start_num + current_count

            for i_offset, idx in enumerate(new_indices):
                uploaded_file = uploaded_files[idx]
                try:
                    current_num = effective_start_num + i_offset
                    num_str = str(current_num).zfill(padding)
                    new_base_name = f"{setting_age}_{num_str}_{setting_status}"
                    
                    image = Image.open(uploaded_file).convert('RGB')
                    original_ext = uploaded_file.name.split('.')[-1].lower()
                    if original_ext == 'jpeg': original_ext = 'jpg'
                    save_format = 'PNG' if original_ext == 'png' else 'JPEG'
                    mime = "image/png" if original_ext == 'png' else "image/jpeg"

                    item_data = {
                        "image": image,
                        "original_name": uploaded_file.name,
                        "current_name": new_base_name,
                        "ext": original_ext,
                        "save_format": save_format,
                        "mime": mime
                    }
                    st.session_state.results[idx] = item_data
                    
                except Exception as e:
                    st.error(f"エラー: {e}")
            
            st.rerun()

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
