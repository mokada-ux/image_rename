import streamlit as st
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
from deep_translator import GoogleTranslator
import io
import zipfile
import re

# --- ページ設定 ---
st.set_page_config(page_title="画像リネームツール Pro+", layout="wide")
st.title("🏷️ 画像リネームツール Pro+ (即時編集版)")

# --- セッション状態の初期化 ---
if 'results' not in st.session_state:
    st.session_state.results = {} # 辞書形式で管理 {index: data}

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
    if " and " in clean_en: # "man and woman" パターン
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
        # index順に並べて格納
        for idx in sorted(results_dict.keys()):
            item = results_dict[idx]
            # 編集後の名前があればそれを使う（st.session_stateのウィジェット値を取得）
            # ただしZip作成時は画面のリロードを挟まないため、
            # 直前の入力値を取得するには `st.session_state[key]` を参照する必要がある
            
            # 辞書内の名前を使用 (UIのcallbackで更新されている前提)
            fname = f"{item['current_name']}.{item['ext']}"
            
            img_byte_arr = io.BytesIO()
            item['image'].save(img_byte_arr, format=item['save_format'])
            zf.writestr(fname, img_byte_arr.getvalue())
    return zip_buffer.getvalue()

# --- コールバック関数: 名前編集時に即座に保存 ---
def update_name(index):
    # テキストボックスの入力値を辞書に反映
    new_val = st.session_state[f"input_{index}"]
    st.session_state.results[index]['current_name'] = new_val


# --- UI構築 ---

with st.sidebar:
    st.header("設定")
    selected_genre = st.selectbox(
        "ジャンルを選択",
        ["ダイエット", "育毛", "美容", "ビジネス", "介護", "その他"],
        index=0
    )
    # リセットボタン（新しいバッチを始める時用）
    if st.button("リセット / 最初から"):
        st.session_state.results = {}
        st.rerun()

st.write("##### 画像アップロード")
st.caption("アップロード後、自動で解析が始まり、順次下に表示されます。表示されたものから編集・DL可能です。")

uploaded_files = st.file_uploader(
    "画像を選択", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

# Zipボタンの場所確保 (上)
top_zip_area = st.empty()

# メイン表示エリア
main_area = st.container()

# Zipボタンの場所確保 (下)
bottom_zip_area = st.empty()


if uploaded_files:
    # 解析実行ボタン
    # (すでに解析済みのファイルがリストにある場合は、再解析せず表示のみ行うロジック)
    if st.button("解析・表示スタート", type="primary"):
        
        with st.spinner('AIモデル読み込み中...'):
            processor, model = load_models()

        progress_bar = st.progress(0)
        
        # ループ処理
        for i, uploaded_file in enumerate(uploaded_files):
            
            # --- 未処理の場合のみAI解析を実行 ---
            if i not in st.session_state.results:
                try:
                    image = Image.open(uploaded_file).convert('RGB')
                    
                    # AI処理
                    inputs = processor(image, return_tensors="pt")
                    out = model.generate(**inputs, max_new_tokens=60, min_length=10, num_beams=3)
                    caption_en = processor.decode(out[0], skip_special_tokens=True)
                    
                    # 命名
                    base_name = analyze_caption(caption_en, selected_genre)
                    
                    # 拡張子等
                    original_ext = uploaded_file.name.split('.')[-1].lower()
                    if original_ext == 'jpeg': original_ext = 'jpg'
                    save_format = 'PNG' if original_ext == 'png' else 'JPEG'
                    mime = "image/png" if original_ext == 'png' else "image/jpeg"

                    # 結果を辞書に保存
                    st.session_state.results[i] = {
                        "image": image,
                        "original_name": uploaded_file.name,
                        "current_name": base_name, # 初期値
                        "ext": original_ext,
                        "save_format": save_format,
                        "mime": mime,
                        "caption_debug": caption_en
                    }
                    
                except Exception as e:
                    st.error(f"{uploaded_file.name} でエラー: {e}")
            
            # --- 画面描画 (処理済みデータがあればここを通る) ---
            # ここで「編集可能なUI」を直接描画します
            item = st.session_state.results[i]
            
            with main_area:
                with st.container():
                    col1, col2, col3 = st.columns([1, 2, 1])
                    
                    # 1. サムネイル
                    with col1:
                        st.image(item['image'], width=150)
                    
                    # 2. 編集エリア
                    with col2:
                        # on_changeで入力確定時に即座に内部データを更新
                        st.text_input(
                            "ファイル名",
                            value=item['current_name'],
                            key=f"input_{i}",
                            on_change=update_name,
                            args=(i,)
                        )
                        st.caption(f"元: {item['original_name']} / AI: {item['caption_debug']}")
                    
                    # 3. 個別DLボタン
                    with col3:
                        final_fname = f"{item['current_name']}.{item['ext']}"
                        img_byte_arr = io.BytesIO()
                        item['image'].save(img_byte_arr, format=item['save_format'])
                        
                        st.write("") # 余白
                        st.download_button(
                            "⬇️ 保存",
                            data=img_byte_arr.getvalue(),
                            file_name=final_fname,
                            mime=item['mime'],
                            key=f"dl_{i}"
                        )
                st.divider()

            # 進捗更新
            progress_bar.progress((i + 1) / len(uploaded_files))

        # --- ループ終了後: Zipボタンの更新 ---
        # 全ての処理が終わった(あるいはキャッシュ表示が終わった)時点でZipボタンを出す
        if
