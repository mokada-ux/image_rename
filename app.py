import streamlit as st
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
from deep_translator import GoogleTranslator
import io
import zipfile
import re

# --- ページ設定 ---
st.set_page_config(page_title="AI広告画像リネームPro", page_icon="🏷️")

st.title("🏷️ AI 広告画像リネーム Pro")
st.write("複数の画像をアップロードすると、ルール（ジャンル_属性_動作）に従って一括リネームします。")

# --- 設定：命名ルール判定ロジック ---
def analyze_caption_to_filename(caption_en):
    """
    AIが生成した英語キャプション(caption_en)から、
    指定ルールに沿った日本語ファイル名を生成する関数
    """
    caption_lower = caption_en.lower()

    # 1. ジャンルの判定 (キーワードマッチング)
    genre = "その他"
    if any(w in caption_lower for w in ['hair', 'head', 'comb', 'bald']):
        genre = "育毛"
    elif any(w in caption_lower for w in ['food', 'eat', 'gym', 'run', 'fat', 'slim', 'salad', 'sport', 'body']):
        genre = "ダイエット"
    elif any(w in caption_lower for w in ['face', 'skin', 'makeup', 'cosmetic', 'smile', 'beautiful']):
        genre = "美容"
    
    # 2. 性別・人数の判定
    target = "人物" # デフォルト
    
    # 家族判定 (family, group, children など)
    if any(w in caption_lower for w in ['family', 'group', 'people', 'children', 'kids']):
        target = "家族"
    # 男女判定 (manとwomanの両方が出たら)
    elif ('man' in caption_lower or 'boy' in caption_lower) and ('woman' in caption_lower or 'girl' in caption_lower):
        target = "男女"
    # 女性判定
    elif any(w in caption_lower for w in ['woman', 'girl', 'lady', 'female']):
        target = "女性"
    # 男性判定 (一応入れておく)
    elif any(w in caption_lower for w in ['man', 'boy', 'guy', 'male']):
        target = "男性"

    # 3. 「何をしているか」 (翻訳APIを使用)
    try:
        # deep-translatorを使って日本語化
        action_jp = GoogleTranslator(source='en', target='ja').translate(caption_en)
        # ファイル名に使えない文字を除去
        action_jp = re.sub(r'[\\/:*?"<>|]', '', action_jp)
        # スペースをアンダーバーに
        action_jp = action_jp.replace(" ", "_")
        # 長すぎる場合は適度にカット (例: 20文字)
        if len(action_jp) > 20:
            action_jp = action_jp[:20]
    except:
        action_jp = "動作不明"

    # 結合して返す
    return f"{genre}_{target}_{action_jp}"

# --- モデルの読み込み ---
@st.cache_resource
def load_model():
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

# --- メイン処理 ---
with st.spinner('AIモデルを準備中...'):
    processor, model = load_model()

# 複数ファイルアップロードを有効化 (accept_multiple_files=True)
uploaded_files = st.file_uploader(
    "画像をまとめてアップロード (複数選択可)", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("一括変換スタート"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # ZIPファイル作成用のバッファ
        zip_buffer = io.BytesIO()
        
        results = [] # 結果表示用リスト

        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"処理中 ({i+1}/{len(uploaded_files)}): {uploaded_file.name}")
                
                try:
                    # 画像読み込み
                    image = Image.open(uploaded_file).convert('RGB')
                    
                    # 1. AIで英語キャプション生成
                    inputs = processor(image, return_tensors="pt")
                    out = model.generate(**inputs, max_new_tokens=50)
                    caption_en = processor.decode(out[0], skip_special_tokens=True)
                    
                    # 2. ルールに基づいてリネーム
                    new_filename_base = analyze_caption_to_filename(caption_en)
                    
                    # 拡張子の処理
                    original_ext = uploaded_file.name.split('.')[-1].lower()
                    if original_ext == 'jpeg': original_ext = 'jpg'
                    new_filename = f"{new_filename_base}.{original_ext}"
                    
                    # 重複回避 (同じ名前になった場合連番をつける)
                    count = 1
                    temp_name = new_filename
                    while any(r['name'] == temp_name for r in results):
                        temp_name = f"{new_filename_base}_{count}.{original_ext}"
                        count += 1
                    new_filename = temp_name

                    # ZIPに追加するための画像データ準備
                    img_byte_arr = io.BytesIO()
                    # JPEG/PNG形式を維持して保存
                    save_fmt = 'PNG' if original_ext == 'png' else 'JPEG'
                    image.save(img_byte_arr, format=save_fmt)
                    
                    # ZIPファイルに書き込み
                    zf.writestr(new_filename, img_byte_arr.getvalue())
                    
                    results.append({"original": uploaded_file.name, "name": new_filename, "desc": caption_en})

                except Exception as e:
                    st.error(f"{uploaded_file.name} の処理中にエラー: {e}")
                
                # 進捗バー更新
                progress_bar.progress((i + 1) / len(uploaded_files))

        status_text.text("完了しました！")
        
        # --- 結果の表示 ---
        st.success(f"{len(results)}枚の画像を処理しました。")
        
        # 一括ダウンロードボタン
        st.download_button(
            label="📦 すべての画像をZIPでダウンロード",
            data=zip_buffer.getvalue(),
            file_name="renamed_images.zip",
            mime="application/zip"
        )
        
        # 詳細リスト表示
        st.write("---")
        st.subheader("変換結果リスト")
        for res in results:
            st.write(f"✅ `{res['original']}` → **`{res['name']}`**")
            # デバッグ用に元のAI認識結果も小さく表示
            st.caption(f"(AI認識原文: {res['desc']})")
