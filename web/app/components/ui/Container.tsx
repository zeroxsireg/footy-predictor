import { cx } from "@/app/lib/cx";

export function Container({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cx("mx-auto w-full max-w-6xl px-4", className)}>
      {children}
    </div>
  );
}
