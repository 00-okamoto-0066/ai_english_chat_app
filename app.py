import os
import time
from anthropic import Anthropic
from dotenv import load_dotenv
import streamlit as st

from prompts import SYSTEM_PROMPTS

from openai import OpenAI
from streamlit_mic_recorder import mic_recorder


try:
    # Streamlit Cloud環境の場合（secretsから環境変数にセット）
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    # ローカル環境の場合（.envファイルから環境変数を読み込む）
    load_dotenv()
    
    
# 環境変数をロードしてクライアントを初期化
client = Anthropic()
openai_client = OpenAI()


# 🧠 Webアプリ専用の記憶の箱（セッションステート）を初期化する
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def slow_stream(stream):
    """少しゆっくり文字を流すための関数"""
    for chunk in stream:
        yield chunk
        time.sleep(0.1)


# 🎛️ サイドバーの処理
with st.sidebar:
    st.header("⚙️ レッスン設定")
    
    selection = st.radio(
        "会話する相手を選んでね",
        ["やさしい先生", "フランクな友達", "ビジネス上司"],
    )
    
    st.markdown("---")  
    
    # ⏺️ 画面にマイクの録音ボタンを設置
    st.markdown("### 🎤 音声で入力する")
    audio_data = mic_recorder(
        start_prompt="音声入力を開始",
        stop_prompt="録音を終了して送信",
        key="mic_input"
    )
    
    st.markdown("---")  
    
    #　🗑️ 会話履歴を削除する
    st.markdown("### 🗑️ 会話履歴を削除する")
    if st.button("🗑️ 会話履歴をリセット"):
        st.session_state.chat_history = []
        st.toast("🗑️ 会話履歴をリセットしました！", icon="✨")
        time.sleep(0.5)
        st.rerun()
        
    st.markdown("---")
    
    # 📕 チャットの履歴を1つの文章にまとめる
    chat_text = ""
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            chat_text += f"🗣️ 【あなた】\n{message['content']}\n"
            chat_text += "----------------------------------------\n\n"
        else:
            chat_text += f"🤖 【{selection}】\n{message['content']}\n"
            chat_text += "----------------------------------------\n\n"
    
    #　💾 会話履歴を保存する
    st.markdown("💾 レッスン内容の保存（ダウンロード）")
    st.download_button(
        label="💾 レッスン内容を保存する",
        data=chat_text,
        file_name="english_lesson_log.txt",  
        mime="text/plain",
    )


# 🤖 選択されたキャラクターに合わせたプロンプトを別ファイルから取り出す
system_prompt = SYSTEM_PROMPTS.get(selection, SYSTEM_PROMPTS["やさしい先生"])


# 📺 画面のタイトルと説明を表示
st.title("💬 英会話レッスン")
st.write(f"現在は **【{selection}】** とお話をしています。相手に合わせた言葉遣いで話してみよう！")   


# 🗣️ 過去の会話の履歴を画面に表示
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# ユーザーからの入力を格納する変数を初期化
user_input = None

# 🎙️ マイクから音声を録音・送信した場合の処理
if audio_data:
    with st.spinner("🎧 音声をテキストに変換中..."):
        audio_bytes = audio_data['bytes']
        
        # 一時的な音声ファイルとして保存する
        audio_file_path = "temp_audio.mp3"
        with open(audio_file_path, "wb") as f:
            f.write(audio_bytes)
        
        # Whisper APIに渡して文字起こしする
        with open(audio_file_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        
        # 文字起こしされたテキストを変数に格納
        user_input = transcript.text
        
        # 使い終わった一時ファイルを削除する
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)

# ⌨️ キーボード入力した内容を受け取り処理
text_input = st.chat_input("英語でメッセージを入力、または上のマイクを使ってみよう！")
if text_input:
    user_input = text_input

            
# 📝 ユーザーからのメッセージを受け取る
# 共通：入力されたテキスト（音声orキーボード）をClaudeに送る処理
if user_input :
    # ユーザーの発言を画面に表示し、履歴に追加
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    
    # Claudeからの返答をストリーミング形式で取得・表示
    with st.chat_message("assistant"):
        with client.messages.stream(
                model="claude-haiku-5-5",
                max_tokens=1000,
                system=system_prompt,
                messages=st.session_state.chat_history
        ) as stream:
            ai_message = st.write_stream(slow_stream(stream.text_stream))

# 🔊 返答テキストを音声（mp3）に変換して自動再生する
    if ai_message:
        # OpenAIのTTSで音声を生成
        speech_response = openai_client.audio.speech.create(
            model="tts-1",  # または "gpt-4o-mini-tts" など
            voice="alloy",  # 声の種類（alloy, echo, fable, onyx, nova, shimmer）
            input=ai_message
        )
        
        # 一時ファイルとして保存
        speech_file_path = "temp_response.mp3"
        speech_response.write_to_file(speech_file_path)
        
        # Streamlitの音声再生プレイヤーを表示（autoplay=Trueで自動再生）
        st.audio(speech_file_path, format="audio/mp3", autoplay=True)

    st.session_state.chat_history.append({"role": "assistant", "content": ai_message})