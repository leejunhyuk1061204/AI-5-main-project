/**
 * 숫자 포맷팅 유틸리티
 * - 천 단위 콤마 적용
 * - 입력 필드 변환
 */

/**
 * 숫자를 천 단위 콤마가 포함된 문자열로 변환
 * @example formatNumberWithCommas(1200) => "1,200"
 */
export const formatNumberWithCommas = (value: number | string): string => {
    const num = typeof value === 'string' ? parseFormattedNumber(value) : value;
    if (isNaN(num) || num === 0) return '';
    return num.toLocaleString('ko-KR');
};

/**
 * 콤마가 포함된 문자열을 숫자로 변환
 * @example parseFormattedNumber("1,200") => 1200
 */
export const parseFormattedNumber = (value: string): number => {
    if (!value) return 0;
    return parseInt(value.replace(/,/g, ''), 10) || 0;
};

/**
 * 입력 중인 값에 실시간으로 콤마 포맷 적용
 * 숫자가 아닌 문자는 제거하고 콤마 추가
 * @example formatInputWithCommas("1200") => "1,200"
 */
export const formatInputWithCommas = (value: string): string => {
    // 숫자가 아닌 문자 제거 (콤마 제외)
    const numericOnly = value.replace(/[^0-9]/g, '');
    if (!numericOnly) return '';

    const num = parseInt(numericOnly, 10);
    if (isNaN(num)) return '';

    return num.toLocaleString('ko-KR');
};
