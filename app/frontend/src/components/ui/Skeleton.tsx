import type { CSSProperties } from "react";

interface Props {
  width?: string | number;
  height?: string | number;
  radius?: string | number;
  style?: CSSProperties;
  className?: string;
}

// 로딩 중 자리표시자(shimmer). "불러오는 중…" 텍스트 대신 실제 콘텐츠 형태를 미리 보여준다.
// prefers-reduced-motion 사용자는 CSS에서 shimmer 애니메이션이 꺼지고 정적 회색으로 표시된다.
export default function Skeleton({ width = "100%", height = 16, radius = 8, style, className }: Props) {
  return (
    <span
      className={"skeleton" + (className ? " " + className : "")}
      style={{ width, height, borderRadius: radius, ...style }}
      aria-hidden
    />
  );
}
