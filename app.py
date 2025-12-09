import streamlit as st
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
from deep_translator import GoogleTranslator
import io
import re

# --- ページ設定 ---
st.set_page_config(page_title="高精度画像リネームツール", layout="wide")
st.title("🏷️ 画像リネームツール Pro (高精度版)")

# --- セッション状態 ---
if 'processed_images' not in st.session_state:
    st.session_state.processed_images = []

# --- AIモデルの読み込み (Largeモデルに変更) ---
@st.cache_resource
def load_model():
    # 'base' から 'large' に変更して精度向上
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")
    return processor, model

# --- ヘルパー関数: キャプションのクリーニング ---
def clean_caption_text(text):
    """翻訳前に英語のノイズを除去して自然な表現にしやすくする"""
    text = text.lower()
    # BLIPモデル特有のハルシネーション（謎単語）や不要な定型句を削除
    remove_words = [
        "arafed", "view of", "close up of", "picture of", "image of", 
        "looking at the camera", "with a white background", "in the background"
    ]
    for w in remove_words:
        text = text.replace(w, "")
    return text.strip()

# --- ヘルパー関数: 解析ロジック ---
def analyze_caption(caption_en, selected_genre):
    # 1. まず英語をきれいにする
    clean_en = clean_caption_text(caption_en)
    
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
    num_dict = {
        'one': '1人', 'two': '2人', 'three': '3人', 'four': '4人', 'five': '5人',
        'couple': '2人', 'pair': '2人', 'group': '複数', 'crowd': '複数'
    }
    # 単語マッチング
    for word, jp_count in num_dict.items():
        if f" {word} " in f" {clean_en} ": # 前後にスペースを入れて単語として判定
            count = jp_count
            break
            
    # --- 動作 (Action) - 翻訳の改善 ---
    try:
        # 文全体ではなく、動詞句や重要な部分を中心に翻訳させる工夫
        # Google翻訳にかける
        action_jp = GoogleTranslator(source='en', target='ja').translate(clean_en)
        
        # 記号削除
        action_jp = re.sub(r'[\\/:*?"<>|]', '', action_jp)
        action_jp = action_jp.replace(" ", "_").replace("　", "_")
        
        # 「〜の」で終わるような変な翻訳をカット (例: 椅子の上の -> 椅子の上)
        if action_jp.endswith("の"):
            action_jp = action_jp[:-1]
            
        # 長すぎる修飾語をカットするための簡易処理
        # (日本語の助詞「で」「に」「を」で区切って、最後の方（動作）だけ残すなど)
        if len(action_jp) > 20:
             action_jp = action_jp[:20]

    except:
        action_jp = "動作不明"

    # 結合 (ジャンル_性別_人数_動作)
    return f"{selected_genre}_{gender}_{count}_{action_jp}"

# --- UI ---
with st.sidebar:
    st.header("設定")
    selected_genre = st.selectbox(
        "ジャンルを選択",
        ["ダイエット", "育毛", "美容", "ビジネス", "介護", "その他"],
        index=0
    )

st.write("##### 1. 画像アップロード")
st.info("※精度向上のため「Largeモデル」を使用しています。解析に少し時間がかかります。")
uploaded_files = st.file_uploader(
    "画像を選択", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("高精度解析スタート", type="primary"):
        st.session_state.processed_images = []
        
        with st.spinner('高精度AIモデルを起動中...'):
            processor, model = load_model()

        progress_bar = st.progress(0)
        
        for i, uploaded_file in enumerate(uploaded_files):
            try:
                image = Image.open(uploaded_file).convert('RGB')
                
                # --- AI生成設定の強化 (ここが重要) ---
                inputs = processor(image, return_tensors="pt")
                
                # num_beams=3: 3つのパターンを考えて一番良いものを選ぶ
                # min_length=15: 短すぎる答えを防ぐ
                out = model.generate(
                    **inputs, 
                    max_new_tokens=50, 
                    min_length=10, 
                    num_beams=3, 
                    repetition_penalty=1.2 # 同じ単語の繰り返し防止
                )
                caption_en = processor.decode(out[0], skip_special_tokens=True)
                
                # 命名生成
                base_name = analyze_caption(caption_en, selected_genre)
                
                # 拡張子など
                original_ext = uploaded_file.name.split('.')[-1].lower()
                if original_ext == 'jpeg': original_ext = 'jpg'
                save_format = 'PNG' if original_ext == 'png' else 'JPEG'
                mime_type = "image/png" if original_ext == 'png' else "image/jpeg"

                st.session_state.processed_images.append({
                    "id": i,
                    "image": image,
                    "original_name": uploaded_file.name,
                    "default_base_name": base_name,
                    "ext": original_ext,
                    "save_format": save_format,
                    "mime_type": mime_type,
                    "caption_debug": caption_en
                })
                
            except Exception as e:
                st.error(f"エラー: {e}")
            
            progress_bar.progress((i + 1) / len(uploaded_files))
        
        st.success("解析完了！")

# --- 結果表示 ---
if st.session_state.processed_images:
    st.write("---")
    st.write("##### 2. 確認・編集・ダウンロード")
    
    for item in st.session_state.processed_images:
        with st.container():
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                st.image(item['image'], width=150)
            with col2:
                new_base_name = st.text_input(
                    "ファイル名", value=item['default_base_name'], key=f"in_{item['id']}"
                )
                # デバッグ用に英語原文も薄く表示（翻訳がおかしい時の確認用）
                st.caption(f"AI原文: {item['caption_debug']}")
            with col3:
                final_name = f"{new_base_name}.{item['ext']}"
                img_byte_arr = io.BytesIO()
                item['image'].save(img_byte_arr, format=item['save_format'])
                st.write("")
                st.write("")
                st.download_button(
                    "⬇️ 保存",
                    data=img_byte_arr.getvalue(),
                    file_name=final_name,
                    mime=item['mime_type'],
                    key=f"dl_{item['id']}"
                )
            st.divider()
