package kr.co.himedia.entity;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum CloudProvider {
    HIGH_MOBILITY("하이 모빌리티");

    private final String description;
}
