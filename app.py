import streamlit as st
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
import io

# --- ページ設定 ---
st.set_page_config(page_title="AI画像リネーム", page_icon="🏷️")

st.title("🏷️ AI 自動画像リネームアプリ")
st.write("画像の内容をAIが解析し、ファイル名を自動生成します。（サーバー実行版）")

# --- モデルの読み込み関数（キャッシュ化） ---
# @st.cache_resource を使うことで、2回目以降の読み込みを爆速にします
@st.cache_resource
def load_model():
    # 軽量なBLIPモデルを使用
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    return processor, model

# --- メイン処理 ---
# 最初にモデルをロード（初回は少し時間がかかります）
with st.spinner('AIモデルをサーバーで起動中... (初回のみ1分ほどかかります)'):
    processor, model = load_model()

uploaded_file = st.file_uploader("画像をドラッグ＆ドロップ", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # 画像を開く
    image = Image.open(uploaded_file).convert('RGB')
    st.image(image, caption="アップロード画像", use_column_width=True)

    if st.button("名前を生成する"):
        with st.spinner('AIが解析中...'):
            try:
                # 1. AI向けに前処理
                inputs = processor(image, return_tensors="pt")

                # 2. キャプション生成
                out = model.generate(**inputs, max_new_tokens=30)
                caption = processor.decode(out[0], skip_special_tokens=True)
                
                # 3. ファイル名に変換 (スペースをアンダーバーに、小文字化)
                # 例: "A dog running" -> "a_dog_running"
                filename_base = caption.replace(" ", "_").lower()
                
                # 記号などを簡易的に削除（英数字と_のみ残す）
                filename_base = "".join([c for c in filename_base if c.isalnum() or c == "_"])
                
                # 元の拡張子を維持
                ext = uploaded_file.name.split('.')[-1]
                new_filename = f"{filename_base}.{ext}"

                st.success("完了しました！")
                st.markdown(f"### 📂 提案ファイル名: `{new_filename}`")

                # ダウンロード準備
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format=image.format)
                img_byte_arr = img_byte_arr.getvalue()

                # ダウンロードボタン
                st.download_button(
                    label="この名前で保存する",
                    data=img_byte_arr,
                    file_name=new_filename,
                    mime=f"image/{ext}"
                )
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")