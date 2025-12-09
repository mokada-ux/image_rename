import streamlit as st
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
from deep_translator import GoogleTranslator
import io
import zipfile
import re

# --- ページ設定 ---
st.set_page_config(page_title="画像リネームツール Pro+", layout="wide")
st.title("🏷️ 画像リネームツール Pro+ (編集維持版)")

# --- セッション状態の初期化 ---
if 'results' not in st.session_state:
    st.session_state.results = {} # {index: data}

# --- モデル読み込み ---
@st.cache_resource
def load_models():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")
    return processor, model

# --- クリーニング関数 ---
def clean_english_caption(text):
    text = text.lower()
    remove_words = [
        "arafed", "view of", "close up of", "picture of", "image of", 
        "looking at the camera", "with a white background", "in the background",
        "there is ", "there are "
    ]
    for w in remove_words:
        text = text.replace(w, "")
    return text.strip()

def clean_japanese_text(text):
    remove_ends = [
        "がいます", "があります", "写っています", 
        "の画像", "の写真", "一枚", "です", "ます", "。", "、"
    ]
    for end in remove_ends:
        text = text.replace(end, "")
    text = re.sub(r'[\\/:*?"<>|]', '', text)
    text = text.replace(" ", "_").replace("　", "_")
    if len(text) > 25:
        text = text[:25]
    return text.strip()

# --- 解析ロジック ---
def analyze_caption(caption_en, selected_genre):
    clean_en = clean_english_caption(caption_en)
    
    # 性別
    gender = "人物"
    if any(w in clean_en for w in ['family', 'group', 'crowd', 'children', 'kids', 'people', 'friends']):
        gender = "家族"
    elif ('man' in clean_en or 'boy' in clean_en) and ('woman' in clean_en or 'girl' in clean_en):
        gender = "男女"
    elif any(w in clean_en for w in ['woman', 'girl', 'lady', 'female', 'bride']):
        gender = "女性"
    elif any(w in clean_en for w in ['man', 'boy', 'guy', 'male']):
        gender = "男性"

    # 人数
    count = "1人"
    if " and " in clean_en: 
        person_words = ['man', 'woman', 'boy', 'girl', 'lady', 'guy', 'person']
        if sum(1 for w in person_words if w in clean_en) >= 2:
            count = "2人"
    
    num_dict = {
        'one': '1人', 'two': '2人', 'three': '3人', 'four': '4人', 'five': '5人',
        'couple': '2人', 'pair': '2人', 'group': '複数', 'crowd': '複数'
    }
    for word, jp_count in num_dict.items():
        if f" {word} " in f" {clean_en} ":
            count = jp_count
            break
    if count == "1人" and (gender in ["家族", "男女"] or "people" in clean_en):
        count = "複数"

    # 動作
    try:
        action_jp = GoogleTranslator(source='en', target='ja').translate(clean_en)
        action_jp = clean_japanese_text(action_jp)
    except:
        action_jp = "動作"

    return f"{selected_genre}_{gender}_{count}_{action_jp}"

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
    # key="input_{index}" の値を取得して保存
    new_val = st.session_state[f"input_{index}"]
    st.session_state.results[index]['current_name'] = new_val

# --- 表示用の関数 (行を描画) ---
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
                on_change=update_name, # 編集確定時に実行
                args=(index,)
            )
            st.caption(f"元: {item['original_name']} / AI: {item['caption_debug']}")
        with col3:
            final_fname = f"{item['current_name']}.{item['ext']}"
            img_byte_arr = io.BytesIO()
            item['image'].save(img_byte_arr, format=item['save_format'])
            st.write("")
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
    st.header("設定")
    selected_genre = st.selectbox(
        "ジャンルを選択",
        ["ダイエット", "育毛・ヘアケア", "美容", "健康", "その他"],
        index=0
    )
    if st.button("リセット / 最初から"):
        st.session_state.results = {}
        st.rerun()

st.write("##### 画像アップロード")

uploaded_files = st.file_uploader(
    "画像を選択", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

# Zipボタン (上)
top_zip_area = st.empty()

# --- メインエリア (常に表示) ---
# ここが重要: ボタンの中に入れず、常に実行する
if st.session_state.results:
    # 既存の解析結果を表示
    # index順に並べて表示
    for i in sorted(st.session_state.results.keys()):
        render_row(i, st.session_state.results[i])

# --- 解析ボタン & 新規処理 ---
if uploaded_files:
    # まだ解析していないファイルがあるかチェック
    processed_ids = st.session_state.results.keys()
    unprocessed_indices = [i for i in range(len(uploaded_files)) if i not in processed_ids]
    
    # 未処理がある場合のみボタンのテキストを変えるなどの工夫も可能
    if unprocessed_indices:
        btn_label = "未解析の画像を解析する"
    else:
        btn_label = "解析スタート (完了済み)"

    if st.button(btn_label, type="primary"):
        
        if not unprocessed_indices:
            st.info("全ての画像は解析済みです。")
        else:
            with st.spinner('AI解析中...'):
                processor, model = load_models()
                progress_bar = st.progress(0)
                
                # 未処理のものだけループ処理
                for i in unprocessed_indices:
                    uploaded_file = uploaded_files[i]
                    try:
                        image = Image.open(uploaded_file).convert('RGB')
                        
                        # AI処理
                        inputs = processor(image, return_tensors="pt")
                        out = model.generate(**inputs, max_new_tokens=60, min_length=10, num_beams=3)
                        caption_en = processor.decode(out[0], skip_special_tokens=True)
                        
                        # 命名
                        base_name = analyze_caption(caption_en, selected_genre)
                        
                        # データ作成
                        original_ext = uploaded_file.name.split('.')[-1].lower()
                        if original_ext == 'jpeg': original_ext = 'jpg'
                        save_format = 'PNG' if original_ext == 'png' else 'JPEG'
                        mime = "image/png" if original_ext == 'png' else "image/jpeg"

                        item_data = {
                            "image": image,
                            "original_name": uploaded_file.name,
                            "current_name": base_name,
                            "ext": original_ext,
                            "save_format": save_format,
                            "mime": mime,
                            "caption_debug": caption_en
                        }
                        
                        # Session Stateに保存
                        st.session_state.results[i] = item_data
                        
                        # ★ここがポイント: 解析直後にその場で描画する
                        # (rerunを待たずにユーザーに見せる)
                        render_row(i, item_data)

                    except Exception as e:
                        st.error(f"{uploaded_file.name} でエラー: {e}")
                    
                    # 進捗バーは全体に対する割合で出すと親切
                    progress_bar.progress((len(st.session_state.results)) / len(uploaded_files))
            
            st.success("すべての解析が完了しました！")
            # 最後に画面をリフレッシュして並び順などを整える（必須ではない）
            # st.rerun() 

# --- Zipボタンの表示更新 ---
# 常に最後にチェックして表示
if st.session_state.results:
    zip_data = create_zip(st.session_state.results)
    
    # 上部ボタン
    top_zip_area.download_button(
        "📦 Zipダウンロード (上)",
        data=zip_data,
        file_name="images_renamed.zip",
        mime="application/zip",
        key="zip_top"
    )
    
    # 下部ボタン
    st.download_button(
        "📦 Zipダウンロード (下)",
        data=zip_data,
        file_name="images_renamed.zip",
        mime="application/zip",
        key="zip_bottom"
    )
