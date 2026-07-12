import { cx } from "@/app/lib/cx";
import { Label } from "./Label";

export function Panel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cx("panel", className)}>{children}</div>;
}

/** A titled panel: bracketed header bar + body. The workhorse container. */
export function SectionBlock({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Panel className={className}>
      <div className="border-b border-line px-3 py-2">
        <Label bracket>{title}</Label>
      </div>
      <div className="p-3">{children}</div>
    </Panel>
  );
}
