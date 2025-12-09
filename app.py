import streamlit as st
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
from deep_translator import GoogleTranslator
import io
import zipfile
import re

# --- ページ設定 ---
st.set_page_config(page_title="画像リネームツール Pro+", layout="wide")
st.title("🏷️ 画像リネームツール Pro+ (自然な日本語版)")

# --- セッション状態 ---
if 'processed_results' not in st.session_state:
    st.session_state.processed_results = []
if 'processing_done' not in st.session_state:
    st.session_state.processing_done = False

# --- AIモデル読み込み (Largeモデル) ---
@st.cache_resource
def load_models():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")
    return processor, model

# --- ヘルパー関数: 英語キャプションの事前掃除 ---
def clean_english_caption(text):
    text = text.lower()
    # 翻訳前に邪魔な英語表現を消す
    remove_words = [
        "arafed", "view of", "close up of", "picture of", "image of", 
        "looking at the camera", "with a white background", "in the background",
        "there is ", "there are " # "There is" から始まる文章構造をここで消しておく
    ]
    for w in remove_words:
        text = text.replace(w, "")
    return text.strip()

# --- ヘルパー関数: 日本語翻訳後の掃除 (ここが重要) ---
def clean_japanese_text(text):
    """
    「〜がいます」「〜の写真」などの不要な文末表現を削除し、
    自然なフレーズにする
    """
    # 1. 明確にNGな文末表現を削除
    # 例: "本を読んでいる女性がいます" -> "本を読んでいる女性"
    remove_ends = [
        "がいます", "があります", "写っています", 
        "の画像", "の写真", "一枚", 
        "です", "ます", "。", "、"
    ]
    for end in remove_ends:
        text = text.replace(end, "")
    
    # 2. 記号をアンダーバーに置換（ファイル名用）
    text = re.sub(r'[\\/:*?"<>|]', '', text)
    text = text.replace(" ", "_").replace("　", "_")

    # 3. 20文字以上の長すぎる修飾はカット（任意）
    if len(text) > 25:
        text = text[:25]
        
    return text.strip()

# --- 解析ロジック ---
def analyze_caption(caption_en, selected_genre):
    # 1. 英語の前処理
    clean_en = clean_english_caption(caption_en)
    
    # --- 性別 (Gender) ---
    gender = "人物"
    if any(w in clean_en for w in ['family', 'group', 'crowd', 'children', 'kids', 'people', 'friends']):
        gender = "家族"
    elif ('man' in clean_en or 'boy' in clean_en) and ('woman' in clean_en or 'girl' in clean_en):
        gender = "男女"
    elif any(w in clean_en for w in ['woman', 'girl', 'lady', 'female', 'bride']):
        gender = "女性"
    elif any(w in clean_en for w in ['man', 'boy', 'guy', 'male']):
        gender = "男性"

    # --- 人数 (Count) ---
    count = "1人"
    # "and" があれば複数系の可能性大
    if " and " in clean_en:
        person_words = ['man', 'woman', 'boy', 'girl', 'lady', 'guy', 'person']
        found_persons = sum(1 for w in person_words if w in clean_en)
        if found_persons >= 2:
            count = "2人" # 詳細は不明だが複数は確定

    # 数字単語チェック
    num_dict = {
        'one': '1人', 'two': '2人', 'three': '3人', 'four': '4人', 'five': '5人',
        'couple': '2人', 'pair': '2人', 'group': '複数', 'crowd': '複数'
    }
    for word, jp_count in num_dict.items():
        if f" {word} " in f" {clean_en} ":
            count = jp_count
            break
            
    # デフォルト補正
    if count == "1人":
        if gender in ["家族", "男女"]:
            count = "複数"
        elif "people" in clean_en:
            count = "複数"

    # --- 動作/内容 (Action) ---
    try:
        # 翻訳実行
        action_jp = GoogleTranslator(source='en', target='ja').translate(clean_en)
        # 日本語クリーニング (がいます削除など)
        action_jp = clean_japanese_text(action_jp)
    except:
        action_jp = "動作"

    # 結合
    return f"{selected_genre}_{gender}_{count}_{action_jp}"


# --- UI構築 ---

with st.sidebar:
    st.header("設定")
    selected_genre = st.selectbox(
        "ジャンルを選択",
        ["ダイエット", "育毛", "美容", "ビジネス", "介護", "その他"],
        index=0
    )

st.write("##### 1. 画像アップロード")
st.caption("処理が終わった画像から順に表示されます。")

uploaded_files = st.file_uploader(
    "画像を選択", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

top_zip_container = st.empty()
results_container = st.container()
bottom_zip_container = st.empty()

if uploaded_files:
    if st.button("解析スタート", type="primary"):
        st.session_state.processed_results = []
        st.session_state.processing_done = False
        top_zip_container.empty()
        bottom_zip_container.empty()
        
        with st.spinner('AIモデル読み込み中...'):
            processor, model = load_models()

        progress_bar = st.progress(0)
        
        # --- 順次処理 ---
        for i, uploaded_file in enumerate(uploaded_files):
            try:
                image = Image.open(uploaded_file).convert('RGB')
                
                # AI処理 (説明文生成)
                inputs = processor(image, return_tensors="pt")
                # max_new_tokensを少し長めに確保して文章を切れないようにする
                out = model.generate(**inputs, max_new_tokens=60, min_length=10, num_beams=3)
                caption_en = processor.decode(out[0], skip_special_tokens=True)
                
                # 命名生成
                base_name = analyze_caption(caption_en, selected_genre)
                
                # 拡張子処理
                original_ext = uploaded_file.name.split('.')[-1].lower()
                if original_ext == 'jpeg': original_ext = 'jpg'
                save_format = 'PNG' if original_ext == 'png' else 'JPEG'
                mime_type = "image/png" if original_ext == 'png' else "image/jpeg"

                result_item = {
                    "id": i,
                    "image": image,
                    "original_name": uploaded_file.name,
                    "default_base_name": base_name,
                    "ext": original_ext,
                    "save_format": save_format,
                    "mime_type": mime_type,
                    "caption_debug": caption_en
                }
                st.session_state.processed_results.append(result_item)
                
                # --- 順次表示 (プレビュー) ---
                with results_container:
                    with st.container():
                        c1, c2 = st.columns([1, 3])
                        with c1:
                            st.image(image, width=120)
                        with c2:
                            st.write(f"**元:** {uploaded_file.name}")
                            st.code(f"{base_name}.{original_ext}", language="text")
                            # デバッグ用にどう翻訳されたか確認（不要なら消してください）
                            st.caption(f"AI: {caption_en}")
                        st.divider()

            except Exception as e:
                st.error(f"{uploaded_file.name} でエラー: {e}")
            
            progress_bar.progress((i + 1) / len(uploaded_files))
        
        st.session_state.processing_done = True
        st.success("完了しました！ 下のリストで編集・ダウンロードできます。")


# --- 完了後の表示 ---
if st.session_state.processing_done and st.session_state.processed_results:
    
    # Zip生成
    def create_zip(current_results):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for item in current_results:
                # Zip内は初期値の名前を使用
                fname = f"{item['default_base_name']}.{item['ext']}"
                img_byte_arr = io.BytesIO()
                item['image'].save(img_byte_arr, format=item['save_format'])
                zf.writestr(fname, img_byte_arr.getvalue())
        return zip_buffer.getvalue()

    zip_data = create_zip(st.session_state.processed_results)

    # --- Zipボタン (上) ---
    top_zip_container.download_button(
        "📦 すべてZipでダウンロード (上)",
        data=zip_data,
        file_name="images_renamed.zip",
        mime="application/zip",
        type="primary"
    )

    # --- Zipボタン (下) ---
    bottom_zip_container.download_button(
        "📦 すべてZipでダウンロード (下)",
        data=zip_data,
        file_name="images_renamed.zip",
        mime="application/zip",
        type="primary"
    )

    # --- 個別編集エリア ---
    st.write("---")
    st.subheader("✏️ 個別編集 & ダウンロード")
    
    for idx, item in enumerate(st.session_state.processed_results):
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            st.image(item['image'], width=150)
        
        with col2:
            new_name = st.text_input(
                "ファイル名", 
                value=item['default_base_name'], 
                key=f"edit_{idx}"
            )
            # 編集内容をstateに反映 (Zip再生成はリロードが必要だが、一応保持)
            item['default_base_name'] = new_name
            
        with col3:
            final_fname = f"{new_name}.{item['ext']}"
            img_byte_arr = io.BytesIO()
            item['image'].save(img_byte_arr, format=item['save_format'])
            st.write("") # スペース調整
            st.download_button(
                "⬇️ 保存",
                data=img_byte_arr.getvalue(),
                file_name=final_fname,
                mime=item['mime_type'],
                key=f"dl_{idx}"
            )
        st.divider()
