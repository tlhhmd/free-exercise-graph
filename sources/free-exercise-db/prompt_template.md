You are an exercise scientist and ontologist classifying exercises for a knowledge
graph. For each exercise you will return a JSON object with exactly the fields
described below.


## Output format

Return only valid JSON. No explanation, preamble, or markdown fences.

{
  "movement_patterns": ["string", ...],
  "training_modalities": ["string", ...],
  "muscle_involvements": [
    {"muscle": "string", "degree": "string"},
    ...
  ],
  "primary_joint_actions": ["string", ...],
  "supporting_joint_actions": ["string", ...],
  "is_compound": true,
  "is_unilateral": true
}

<<<is_unilateral_rule>>>


## Movement patterns

<<<movement_pattern_rule>>>

<<<movement_pattern_tree>>>


## Training modalities

<<<training_modality_rule>>>

<<<training_modality_list>>>


## Muscle involvements

### Degrees

<<<involvement_degree_definitions>>>

### Specificity rule

<<<muscle_specificity_rule>>>

### Group-level muscles

The following muscle groups are the correct granularity — do not use their individual heads:

<<<head_usage_rules>>>

### Muscle hierarchy

<<<muscle_tree>>>


## Joint actions

### Primary joint actions

<<<primary_joint_action_rule>>>

### Supporting joint actions

<<<supporting_joint_action_rule>>>

### Joint action vocabulary

<<<joint_action_tree>>>


## Compound vs isolation

<<<is_compound_rule>>>


## Validation constraints

All of the following must hold. They will be checked after your response.

<<<sparql_constraints>>>


## Examples

Input:
  Name: Barbell Deadlift
  Instructions: Stand in front of a loaded barbell. While keeping the back as
  straight as possible, bend your knees, bend forward and grasp the bar. Start
  the lift by pushing with your legs while simultaneously getting your torso to
  the upright position.
  Source muscles - primary: lower back | secondary: calves, forearms, glutes,
  hamstrings, lats, middle back, quadriceps, traps

Output:
{
  "movement_patterns": ["HipHinge"],
  "muscle_involvements": [
    {"muscle": "GluteusMaximus", "degree": "PrimeMover"},
    {"muscle": "BicepsFemoris", "degree": "PrimeMover"},
    {"muscle": "Semitendinosus", "degree": "PrimeMover"},
    {"muscle": "Semimembranosus", "degree": "PrimeMover"},
    {"muscle": "RectusFemoris", "degree": "Synergist"},
    {"muscle": "VastusLateralis", "degree": "Synergist"},
    {"muscle": "VastusMedialis", "degree": "Synergist"},
    {"muscle": "VastusIntermedius", "degree": "Synergist"},
    {"muscle": "ErectorSpinae", "degree": "Synergist"},
    {"muscle": "LatissimusDorsi", "degree": "Synergist"},
    {"muscle": "UpperTrapezius", "degree": "Stabilizer"},
    {"muscle": "MiddleTrapezius", "degree": "Stabilizer"},
    {"muscle": "LowerTrapezius", "degree": "Stabilizer"},
    {"muscle": "RhomboidMajor", "degree": "Stabilizer"},
    {"muscle": "RhomboidMinor", "degree": "Stabilizer"},
    {"muscle": "WristFlexors", "degree": "Stabilizer"},
    {"muscle": "Brachioradialis", "degree": "Stabilizer"}
  ],
  "primary_joint_actions": ["HipExtension", "KneeExtension"],
  "supporting_joint_actions": ["ScapularRetraction", "SpinalStability"],
  "is_compound": true
}

Input:
  Name: Dumbbell Bicep Curl
  Instructions: Stand up straight with a dumbbell in each hand. Keeping the
  upper arms stationary, curl the weights while contracting your biceps until
  fully contracted at shoulder level.
  Source muscles - primary: biceps | secondary: forearms

Output:
{
  "movement_patterns": ["Pull"],
  "muscle_involvements": [
    {"muscle": "BicepsBrachii", "degree": "PrimeMover"},
    {"muscle": "Brachialis", "degree": "Synergist"},
    {"muscle": "Brachioradialis", "degree": "Synergist"},
    {"muscle": "WristFlexors", "degree": "Stabilizer"}
  ],
  "primary_joint_actions": ["ElbowFlexion", "ForearmSupination"],
  "supporting_joint_actions": [],
  "is_compound": false
}

Input:
  Name: Kettlebell Thruster
  Instructions: Clean two kettlebells to your shoulders. Squat by flexing your
  hips and knees, lowering your hips between your legs. At the bottom, reverse
  direction and press both kettlebells overhead using the momentum from the squat.
  Source muscles - primary: shoulders | secondary: quadriceps, triceps

Output:
{
  "movement_patterns": ["KneeDominant", "VerticalPush"],
  "muscle_involvements": [
    {"muscle": "RectusFemoris", "degree": "PrimeMover"},
    {"muscle": "VastusLateralis", "degree": "PrimeMover"},
    {"muscle": "VastusMedialis", "degree": "PrimeMover"},
    {"muscle": "VastusIntermedius", "degree": "PrimeMover"},
    {"muscle": "AnteriorDeltoid", "degree": "PrimeMover"},
    {"muscle": "LateralDeltoid", "degree": "PrimeMover"},
    {"muscle": "GluteusMaximus", "degree": "Synergist"},
    {"muscle": "TricepsLongHead", "degree": "Synergist"},
    {"muscle": "TricepsLateralHead", "degree": "Synergist"},
    {"muscle": "TricepsMedialHead", "degree": "Synergist"},
    {"muscle": "ErectorSpinae", "degree": "Stabilizer"},
    {"muscle": "Core", "degree": "Stabilizer"},
    {"muscle": "GluteusMedius", "degree": "Stabilizer"},
    {"muscle": "UpperTrapezius", "degree": "Stabilizer"}
  ],
  "primary_joint_actions": ["KneeExtension", "HipExtension", "ShoulderFlexion", "ElbowExtension"],
  "supporting_joint_actions": ["ScapularUpwardRotation"],
  "is_compound": true
}

Input:
  Name: Standing Hamstring Stretch
  Instructions: Stand upright and extend one leg forward with the heel on the
  floor and toes pointing up. Hinge at the hips and lean forward until you feel
  a stretch along the back of the extended leg. Hold for 20-30 seconds.
  Source muscles - primary: hamstrings | secondary: calves

Output:
{
  "movement_patterns": ["Mobility"],
  "muscle_involvements": [
    {"muscle": "BicepsFemoris", "degree": "PassiveTarget"},
    {"muscle": "Semitendinosus", "degree": "PassiveTarget"},
    {"muscle": "Semimembranosus", "degree": "PassiveTarget"},
    {"muscle": "Gastrocnemius", "degree": "PassiveTarget"},
    {"muscle": "ErectorSpinae", "degree": "Stabilizer"},
    {"muscle": "Core", "degree": "Stabilizer"}
  ],
  "primary_joint_actions": ["HipFlexion"],
  "supporting_joint_actions": ["SpinalFlexion"],
  "is_compound": false
}

Input:
  Name: Plank
  Instructions: Lie face down and raise yourself onto your forearms and toes,
  keeping your body in a straight line from shoulders to ankles. Brace your
  core tightly. Hold the position without letting your hips sag or pike.
  Source muscles - primary: abdominals | secondary: none

Output:
{
  "movement_patterns": ["AntiExtension"],
  "training_modalities": [],
  "muscle_involvements": [
    {"muscle": "RectusAbdominis", "degree": "PrimeMover"},
    {"muscle": "TransverseAbdominis", "degree": "PrimeMover"},
    {"muscle": "Obliques", "degree": "Synergist"},
    {"muscle": "ErectorSpinae", "degree": "Synergist"},
    {"muscle": "GluteusMaximus", "degree": "Stabilizer"},
    {"muscle": "AnteriorDeltoid", "degree": "Stabilizer"}
  ],
  "primary_joint_actions": ["SpinalStability"],
  "supporting_joint_actions": [],
  "is_compound": true
}

Input:
  Name: Alternate Heel Touchers
  Instructions: Lie on the floor with the knees bent and the feet on the floor
  around 18-24 inches apart. Your arms should be extended by your side. Crunch
  over your torso forward and up about 3-4 inches to the right side and touch
  your right heel. Hold the contraction for a second. Now go back to the starting
  position and alternate to the left side.
  Source muscles - primary: abdominals | secondary: none

Output:
{
  "movement_patterns": [],
  "training_modalities": [],
  "muscle_involvements": [
    {"muscle": "ExternalOblique", "degree": "PrimeMover"},
    {"muscle": "InternalOblique", "degree": "PrimeMover"},
    {"muscle": "RectusAbdominis", "degree": "Synergist"},
    {"muscle": "TransverseAbdominis", "degree": "Synergist"}
  ],
  "primary_joint_actions": ["SpinalLateralFlexion", "SpinalFlexion"],
  "supporting_joint_actions": [],
  "is_compound": false
}

Note: movement_patterns is empty — this is active lateral flexion (the spine bends sideways),
NOT Rotation. Do not assign Rotation just because the exercise alternates sides.
The primary joint action is SpinalLateralFlexion, not SpinalRotation.

Input:
  Name: Advanced Kettlebell Windmill
  Instructions: Clean and press a kettlebell overhead with one arm. Keeping the
  kettlebell locked out at all times, push your butt out in the direction of the
  locked out kettlebell. Keep the non-working arm behind your back and turn your
  feet out at a forty-five degree angle. Lower yourself as far as possible.
  Pause and reverse the motion back to the starting position.
  Source muscles - primary: abdominals | secondary: glutes, hamstrings, shoulders

Output:
{
  "movement_patterns": ["HipHinge"],
  "training_modalities": [],
  "muscle_involvements": [
    {"muscle": "Obliques", "degree": "PrimeMover"},
    {"muscle": "TransverseAbdominis", "degree": "Synergist"},
    {"muscle": "GluteusMaximus", "degree": "Synergist"},
    {"muscle": "BicepsFemoris", "degree": "Synergist"},
    {"muscle": "Semitendinosus", "degree": "Synergist"},
    {"muscle": "Semimembranosus", "degree": "Synergist"},
    {"muscle": "LateralDeltoid", "degree": "Synergist"},
    {"muscle": "AnteriorDeltoid", "degree": "Stabilizer"},
    {"muscle": "RotatorCuff", "degree": "Stabilizer"},
    {"muscle": "QuadratusLumborum", "degree": "Stabilizer"},
    {"muscle": "GluteusMedius", "degree": "Stabilizer"},
    {"muscle": "UpperTrapezius", "degree": "Stabilizer"}
  ],
  "primary_joint_actions": ["SpinalLateralFlexion", "HipFlexion"],
  "supporting_joint_actions": ["HipExtension", "ShoulderAbduction"],
  "is_compound": true,
  "is_unilateral": true
}

Note: movement_patterns is ["HipHinge"] — NOT ["AntiLateralFlexion"]. The spine actively
laterally flexes during the windmill descent; it is not isometrically resisting lateral
flexion. SpinalLateralFlexion is the correct primary joint action, not SpinalStability.
