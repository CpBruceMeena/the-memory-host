import React from "react";
import { Composition } from "remotion";
import { ArchitectureDiagram } from "./ArchitectureDiagram";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ArchitectureDiagram"
        component={ArchitectureDiagram}
        durationInFrames={1}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
