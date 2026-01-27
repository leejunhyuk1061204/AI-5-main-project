# ai/app/services/audio_enhancement.py
"""
오디오 소음 제거 서비스 (Audio Denoising with U-Net)
주행 소음 및 엔진 간섭음을 제거하여 진단 정확도를 높임.
"""
import torch
import torch.nn as nn
import numpy as np
import librosa

class UNetDenoiser(nn.Module):
    """
    Spectrogram 기반 오디오 Denoising을 위한 가벼운 U-Net
    """
    def __init__(self):
        super(UNetDenoiser, self).__init__()
        
        # Encoder
        self.enc1 = self.conv_block(1, 16)
        self.enc2 = self.conv_block(16, 32)
        self.enc3 = self.conv_block(32, 64)
        
        self.pool = nn.MaxPool2d(2)
        
        # Middle
        self.mid = self.conv_block(64, 128)
        
        # Decoder
        self.up3 = nn.ConvTranspose2d(128, 64, kernel_size=2, stride=2)
        self.dec3 = self.conv_block(128, 64)
        
        self.up2 = nn.ConvTranspose2d(64, 32, kernel_size=2, stride=2)
        self.dec2 = self.conv_block(64, 32)
        
        self.up1 = nn.ConvTranspose2d(32, 16, kernel_size=2, stride=2)
        self.dec1 = self.conv_block(32, 16)
        
        self.final = nn.Conv2d(16, 1, kernel_size=1)
        self.sigmoid = nn.Sigmoid()

    def conv_block(self, in_ch, out_ch):
        return nn.Sequential(
            nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        e1 = self.enc1(x)
        p1 = self.pool(e1)
        
        e2 = self.enc2(p1)
        p2 = self.pool(e2)
        
        e3 = self.enc3(p2)
        p3 = self.pool(e3)
        
        m = self.mid(p3)
        
        d3 = self.up3(m)
        d3 = torch.cat([d3, e3], dim=1)
        d3 = self.dec3(d3)
        
        d2 = self.up2(d3)
        d2 = torch.cat([d2, e2], dim=1)
        d2 = self.dec2(d2)
        
        d1 = self.up1(d2)
        d1 = torch.cat([d1, e1], dim=1)
        d1 = self.dec1(d1)
        
        return self.sigmoid(self.final(d1)) * x  # Masking approach

async def denoise_audio(audio_array: np.ndarray, sr: int = 16000) -> np.ndarray:
    """
    U-Net 모델을 사용하여 오디오 소음 제거
    """
    # 1. Mel-Spectrogram 변환
    stft = librosa.stft(audio_array)
    magnitude, phase = librosa.magphase(stft)
    
    # 2. 모델 추론
    clean_mag = magnitude
    
    import os
    weights_path = "ai/weights/audio/denoiser_best.pt"
    
    if os.path.exists(weights_path):
        try:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model = UNetDenoiser().to(device)
            model.load_state_dict(torch.load(weights_path, map_location=device))
            model.eval()
            
            # Prepare Input Tensor (Add Channel & Batch Dim)
            # magnitude shape: (1025, Time)
            mag_tensor = torch.from_numpy(magnitude).float().unsqueeze(0).unsqueeze(0).to(device)
            
            # Inference
            with torch.no_grad():
                 # Resize if needed (U-Net input size constraint) or use padding
                 # For simplicity, we pass directly (assuming input size matches or model handles it)
                 denoised_mag_tensor = model(mag_tensor)
            
            clean_mag = denoised_mag_tensor.squeeze().cpu().numpy()
            print(f"[Denoiser] AI Denoising Applied (Device: {device})")
            
        except Exception as e:
            print(f"[Denoiser Error] Model inference failed: {e}")
            clean_mag = magnitude
    else:
        print(f"[Denoiser] Weights not found ({weights_path}). Using Pass-through.")

    # 3. Inverse STFT로 복구
    clean_stft = clean_mag * phase
    clean_audio = librosa.istft(clean_stft)
    
    return clean_audio

def calculate_si_sdr(reference, estimated):
    """SI-SDR (Source-to-Interference Signal-to-Distortion Ratio) 계산"""
    reference = reference.flatten()
    estimated = estimated.flatten()
    
    alpha = np.dot(reference, estimated) / (np.linalg.norm(reference)**2 + 1e-8)
    target = alpha * reference
    noise = estimated - target
    
    si_sdr = 10 * np.log10(np.linalg.norm(target)**2 / (np.linalg.norm(noise)**2 + 1e-8))
    return si_sdr
