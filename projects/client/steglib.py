from stegano import lsb
import base64

#信息隐藏
def hide_text_and_file_in_image(carrier_image_path, text, file_path, output_image_path):
    """
    将文本和文件一起隐藏在载体图片中，并保存加密后的图片。
    """
    # 读取并base64编码文件内容
    with open(file_path, "rb") as f:
        file_data_b64 = base64.b64encode(f.read()).decode("utf-8")
    
    # 拼接消息
    combined_message = f"[TEXT]{text}[/TEXT][FILE]{file_data_b64}[/FILE]"
    
    # 加密并保存图片
    encoded_image = lsb.hide(carrier_image_path, combined_message)
    encoded_image.save(output_image_path)


def reveal_text_from_image(stego_image_path):
    """
    从图像中提取隐藏的文本信息。
    """
    hidden_message = lsb.reveal(stego_image_path)
    if not hidden_message:
        return None
    
    # 提取 [TEXT]...[/TEXT] 部分的内容
    start = hidden_message.find("[TEXT]") + len("[TEXT]")
    end = hidden_message.find("[/TEXT]")
    return hidden_message[start:end] if start != -1 and end != -1 else None
