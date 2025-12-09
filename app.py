import streamlit as st
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
from deep_translator import GoogleTranslator
import io
import re

# --- ページ設定 ---
st.set_page_config(page_title="画像リネームツール", layout="wide")
st.title("🏷️ 画像リネームツール (編集・個別DL機能付)")

# --- セッション状態の初期化 ---
# 解析結果を保持するために必要
if 'processed_images' not in st.session_state:
    st.session_state.processed_images = []

# --- AIモデルの読み込み ---
@st.cache_resource
def load_model():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

# --- ヘルパー関数: 英語キャプションから要素を抽出 ---
def analyze_caption(caption_en, selected_genre):
    caption_lower = caption_en.lower()
    
    # 1. 性別 (Gender)
    # デフォルト
    gender = "人物"
    
    # 家族・グループ判定 (優先度高)
    if any(w in caption_lower for w in ['family', 'group', 'crowd', 'children', 'kids', 'people']):
        gender = "家族"
    # 男女混合
    elif ('man' in caption_lower or 'boy' in caption_lower) and ('woman' in caption_lower or 'girl' in caption_lower):
        gender = "男女"
    # 女性
    elif any(w in caption_lower for w in ['woman', 'girl', 'lady', 'female']):
        gender = "女性"
    # 男性
    elif any(w in caption_lower for w in ['man', 'boy', 'guy', 'male']):
        gender = "男性"

    # 2. 人数 (Count)
    count = "1人" # デフォルト
    
    # 数字単語の辞書
    num_dict = {
        'one': '1人', 'a ': '1人', 'an ': '1人',
        'two': '2人', 'couple': '2人', 'pair': '2人',
        'three': '3人', 'four': '4人', 'five': '5人',
        'six': '6人', 'seven': '7人', 'eight': '8人', 'nine': '9人', 'ten': '10人'
    }
    
    # キャプションから数字を探す
    found_count = False
    tokens = caption_lower.split()
    for token in tokens:
        if token in num_dict:
            count = num_dict[token]
            found_count = True
            break
    
    # 単語が見つからず、複数形の兆候がある場合
    if not found_count:
        if gender == "家族" or gender == "男女":
            count = "複数"
        elif "people" in caption_lower:
            count = "複数"

    # 3. 動作 (Action) - 翻訳
    try:
        action_jp = GoogleTranslator(source='en', target='ja').translate(caption_en)
        action_jp = re.sub(r'[\\/:*?"<>|]', '', action_jp) # ファイル名禁止文字削除
        action_jp = action_jp.replace(" ", "_")
        if len(action_jp) > 15: # 長すぎる場合はカット
            action_jp = action_jp[:15]
    except:
        action_jp = "動作"

    # 結合して返す (ジャンル_性別_人数_動作)
    return f"{selected_genre}_{gender}_{count}_{action_jp}"

# --- メインUI ---

# サイドバー: 設定など
with st.sidebar:
    st.header("設定")
    # ジャンル選択 (ユーザー指定)
    selected_genre = st.selectbox(
        "ジャンルを選択してください",
        ["ダイエット", "育毛", "美容", "ビジネス", "介護", "その他"],
        index=0
    )

# メインエリア
st.write("##### 1. 画像アップロード")
uploaded_files = st.file_uploader(
    "リネームしたい画像を選択 (複数可)", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

# 解析ボタン
if uploaded_files:
    if st.button("画像を解析して名前を付ける", type="primary"):
        st.session_state.processed_images = [] # リセット
        
        # モデルロード
        with st.spinner('AIモデルを準備中...'):
            processor, model = load_model()

        # 解析ループ
        progress_bar = st.progress(0)
        for i, uploaded_file in enumerate(uploaded_files):
            try:
                # 画像読み込み
                image = Image.open(uploaded_file).convert('RGB')
                
                # AI解析
                inputs = processor(image, return_tensors="pt")
                out = model.generate(**inputs, max_new_tokens=50)
                caption_en = processor.decode(out[0], skip_special_tokens=True)
                
                # 命名生成
                base_name = analyze_caption(caption_en, selected_genre)
                
                # 拡張子処理
                original_ext = uploaded_file.name.split('.')[-1].lower()
                if original_ext == 'jpeg': original_ext = 'jpg'
                
                # 保存形式の判定
                save_format = 'PNG' if original_ext == 'png' else 'JPEG'
                mime_type = "image/png" if original_ext == 'png' else "image/jpeg"

                # データ保持
                st.session_state.processed_images.append({
                    "id": i,
                    "image": image,
                    "original_name": uploaded_file.name,
                    "default_base_name": base_name, # 初期値
                    "ext": original_ext,
                    "save_format": save_format,
                    "mime_type": mime_type,
                    "caption_debug": caption_en
                })
                
            except Exception as e:
                st.error(f"{uploaded_file.name} のエラー: {e}")
            
            progress_bar.progress((i + 1) / len(uploaded_files))
        
        st.success("解析完了！下の一覧から確認・編集してください。")

# --- 結果表示と編集エリア ---
if st.session_state.processed_images:
    st.write("---")
    st.write("##### 2. 確認・編集・ダウンロード")
    st.info("ファイル名を変更してからダウンロードボタンを押すと、変更後の名前で保存されます。")

    # グリッド表示っぽく見せるためのスタイル調整
    for item in st.session_state.processed_images:
        with st.container():
            col1, col2, col3 = st.columns([1, 2, 1])
            
            # 左カラム: サムネイル
            with col1:
                st.image(item['image'], width=150)
                st.caption(f"元: {item['original_name']}")
            
            # 中央カラム: 命名編集 (拡張子なし)
            with col2:
                # keyにIDを含めることで、各画像の入力欄を識別する
                new_base_name = st.text_input(
                    "ファイル名 (拡張子なし)",
                    value=item['default_base_name'],
                    key=f"input_{item['id']}"
                )
                st.caption(f"AI認識: {item['caption_debug']}")

            # 右カラム: ダウンロードボタン
            with col3:
                # 最終的なファイル名を結合
                final_filename = f"{new_base_name}.{item['ext']}"
                
                # 画像データをバイト列に変換
                img_byte_arr = io.BytesIO()
                item['image'].save(img_byte_arr, format=item['save_format'])
                img_data = img_byte_arr.getvalue()
                
                st.write("") # レイアウト調整用の空白
                st.write("") 
                st.download_button(
                    label="⬇️ ダウンロード",
                    data=img_data,
                    file_name=final_filename,
                    mime=item['mime_type'],
                    key=f"btn_{item['id']}"
                )
            st.divider() # 区切り線
