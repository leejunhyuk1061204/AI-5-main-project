package kr.co.himedia.entity;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum CloudProvider {
    SMARTCAR("스마트카"),
    HIGH_MOBILITY("하이모빌리티");

    private final String description;
}
