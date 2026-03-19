# **Kinesiological Taxonomy and Mechanical Classification of Resistance Training Exercises**

The construction of a robust knowledge graph for resistance training necessitates a high-fidelity ontological framework capable of reconciling anatomical precision with the practical nomenclature of the strength and conditioning industry. At the core of this framework lies the joint action, the fundamental unit of osteokinematic description that defines how bones move relative to one another through three-dimensional space.1 For a knowledge graph to be programmatically useful, it must account for the reality that exercise names—the "lexical tokens" of the gym—often mask complex, multi-planar interactions where the primary mechanical driver may vary based on equipment, grip, and individual anthropometry.2 This report provides a controlled vocabulary of joint actions across the human kinetic chain, specifically optimized for classifying resistance training, bodyweight exercises, and mobility work within a gym context.

## **Foundations of Mechanical Classification**

Mechanical classification in the gym environment is traditionally bifurcated into single-joint (isolation) and multi-joint (compound) movements.4 Single-joint exercises, such as the leg extension or biceps curl, are characterized by a primary lever rotating around a single axis of rotation, making them the "atomic" units of the knowledge graph.7 Multi-joint exercises, such as the squat or bench press, involve the coordinated sequencing of multiple segments along a kinetic chain.7 These are further subdivided by their kinetic chain state: open kinetic chain (OKC) movements, where the distal segment moves freely (e.g., a leg curl), and closed kinetic chain (CKC) movements, where the distal segment is fixed (e.g., a deadlift).1

The direction of resistance relative to the joint’s axis determines the "concentric" phase of the exercise, which is the gold standard for identifying the primary joint action.2 In the concentric phase, the load moves against the force of gravity or an external resistance (e.g., a cable stack), and the prime mover muscles shorten to produce the intended motion.2 However, a significant challenge in programmatic classification arises from the "relative vs. real" motion problem.11 In a squat, for example, the femur moves relative to the pelvis (hip flexion/extension) while the tibia moves relative to the femur (knee flexion/extension).13 A knowledge graph must distinguish between these "relative" joint actions and the "real" bone movements to accurately represent the mechanical load on specific tissues.11

## **The Scapulothoracic Joint: The Foundation of Upper Body Mechanics**

The scapulothoracic (ST) joint is not a traditional synovial joint but a functional articulation where the scapula "floats" on the posterior rib cage.15 It serves as the stable base for all glenohumeral (shoulder) movements.17 In resistance training, ST actions are often categorized as "scapular" or "shoulder girdle" movements and are critical for classifying pulling and pushing variations.10 Proper classification here is often undermined by the common use of the term "shoulders" to describe both the humerus and the scapula.18

### **Controlled Vocabulary: Scapulothoracic Actions**

| Name | Exercise Science Definition | Representative Exercises | Commonly Confused With | Unreliable to Classify Programmatically? |
| :---- | :---- | :---- | :---- | :---- |
| Scapular Retraction | Moving the shoulder blades toward the spine, effectively "pinching" them together. | Seated Row, Face Pull, Band Pull-Apart.15 | Shoulder Horizontal Abduction; retraction is the medial glide of the scapula itself, not the humerus moving back. | **Yes** — "Rows" often imply both; the name rarely specifies if the driver is the scapula or the humerus. |
| Scapular Protraction | Moving the shoulder blades away from the spine and forward around the rib cage. | Push-Up Plus, Serratus Punch, Plank.15 | Shoulder Horizontal Adduction; protraction is the lateral glide of the blade, not the arm crossing the chest. | No |
| Scapular Elevation | Moving the shoulder blades upward toward the ears in a shrugging motion. | Dumbbell Shrug, Barbell Shrug, Farmer’s Carry.15 | Neck Extension; shrugging moves the scapula, whereas extension moves the skull/cervical spine. | No |
| Scapular Depression | Moving the shoulder blades downward away from the ears toward the hips. | Scapular Pull-Up (initiation), Dip (active), Lat Pulldown.15 | Shoulder Extension; depression is the inferior glide of the scapula, often initiating a pull. | No |
| Scapular Upward Rotation | Rotating the scapula so the socket (glenoid) points upward to allow overhead reach. | Overhead Press, Lateral Raise, Pull-Up.15 | Scapular Elevation; upward rotation is a circular spin, whereas elevation is a linear lift. | No |
| Scapular Downward Rotation | Rotating the scapula so the socket (glenoid) points downward, returning from overhead. | Pull-Up (concentric), Lat Pulldown, Seated Row.10 | Scapular Depression; downward rotation is the rotational return of the blade. | No |
| Scapular Posterior Tipping | Tilting the top of the scapula backward away from the rib cage around a transverse axis. | Scapular Wall Slide, Overhead Press (end-range), Y-Raise.15 | Scapular Retraction; tipping is a sagittal-plane tilt, while retraction is a frontal-plane glide. | **Yes** — Extremely subtle; almost never detailed in standard exercise instructions. |
| Scapular Anterior Tipping | Tilting the top of the scapula forward toward the ribs, often associated with a "rounded" posture. | Chest Stretch (passive), Rounded-Back Row (compensation).15 | Scapular Protraction; anterior tipping is a tilt, while protraction is a forward glide. | **Yes** — Often a compensatory movement rather than a programmed driver. |

The integration of scapular actions into a knowledge graph allows for the disambiguation of "Upper Body Pull" movements.10 For instance, a "Wide Grip Row" is a composite of shoulder horizontal abduction and scapular retraction, whereas a "Close Grip Row" may emphasize shoulder extension and scapular downward rotation.10 The 2:1 ratio of humeral to scapular movement—scapulohumeral rhythm—means that any classification of the "shoulder" without its corresponding "scapular" action is mechanically incomplete.16

## **The Glenohumeral Joint: Tri-Axial Shoulder Dynamics**

The glenohumeral (GH) joint is a ball-and-socket synovial joint providing three degrees of freedom: rotation around the sagittal, frontal, and transverse axes.18 Because of its high mobility, it is the most complex joint to classify programmatically.17 The GH joint’s orientation is not perfectly aligned with the cardinal planes; the "Scapular Plane" (scaption) sits approximately ![][image1] to ![][image2] anterior to the frontal plane.16 Movements in this plane, such as a "Scapular Plane Raise," are safer and more mechanically efficient than pure frontal plane abduction.16

### **Controlled Vocabulary: Glenohumeral Actions**

| Name | Exercise Science Definition | Representative Exercises | Commonly Confused With | Unreliable to Classify Programmatically? |
| :---- | :---- | :---- | :---- | :---- |
| Shoulder Flexion | Moving the arm forward and upward in the sagittal plane. | Front Raise, Overhead Press (neutral grip), Dead Bug.16 | Shoulder Abduction; both raise the arm but in different planes (anterior vs. lateral). | **Yes** — "Shoulder Press" can be flexion or abduction depending on grip. |
| Shoulder Extension | Moving the arm downward and backward in the sagittal plane. | Straight-Arm Pulldown, Dumbbell Row, Lat Pulldown.19 | Scapular Depression; extension moves the humerus, whereas depression moves the blade. | No |
| Shoulder Abduction | Moving the arm away from the midline of the body in the frontal plane. | Lateral Raise, Wide-Grip Overhead Press, Pull-Up.10 | Shoulder Flexion; distinguished by the lateral rather than forward path. | **Yes** — Exercises like "Raises" are frequently misidentified in names. |
| Shoulder Adduction | Moving the arm toward the midline of the body in the frontal plane. | Cable Adduction, Lat Pulldown (wide grip), Machine Fly.10 | Shoulder Extension; adduction occurs in the frontal plane, extension in the sagittal. | No |
| Internal (Medial) Rotation | Rotating the humerus toward the midline around its long axis. | Band Internal Rotation, Seated Machine Press (as a stabilizer).16 | Scapular Protraction; internal rotation involves the humerus spinning in the socket. | **Yes** — Often an incidental or "hidden" action in pressing. |
| External (Lateral) Rotation | Rotating the humerus away from the midline around its long axis. | Face Pull, Band Pull-Apart, Side-Lying External Rotation.16 | Scapular Retraction; external rotation focuses on the posterior cuff rotation. | No |
| Horizontal Adduction | Moving the arm toward the midline in the transverse plane with the arm flexed at ![][image3]. | Bench Press, Push-Up, Chest Fly.10 | Shoulder Flexion; horizontal adduction requires the arm to start in an abducted position. | No |
| Horizontal Abduction | Moving the arm away from the midline in the transverse plane with the arm flexed at ![][image3]. | Rear Delt Fly, Reverse Cable Fly, Face Pull.10 | Scapular Retraction; horizontal abduction is the humeral movement away from the chest. | **Yes** — "Rows" often combine this with retraction indistinguishably. |

In programmatic classification, "Horizontal Abduction" and "Horizontal Extension" are frequently used as synonyms, but "Horizontal Abduction" is preferred for its clarity regarding the plane of motion.27 A significant ambiguity exists with the term "Shoulder Press".2 A wide-grip barbell press occurs primarily in the frontal plane (abduction), while a close-grip dumbbell press with palms facing each other occurs in the sagittal plane (flexion).2 The knowledge graph must therefore utilize "Grip Width" and "Grip Orientation" as modifier nodes to correctly assign the joint action.2

## **The Upper Extremity: Elbow, Forearm, and Wrist**

The distal joints of the upper extremity—the elbow, radioulnar (forearm), and radiocarpal (wrist) joints—are essential for mediating the interaction between the torso and the weight being lifted.29 While these joints are often treated as simple hinges or pivots, their combined actions define the complexity of grip and the transfer of force in movements like the "Zottman Curl".29

### **Controlled Vocabulary: Elbow and Forearm Actions**

| Name | Exercise Science Definition | Representative Exercises | Commonly Confused With | Unreliable to Classify Programmatically? |
| :---- | :---- | :---- | :---- | :---- |
| Elbow Flexion | Decreasing the angle between the upper arm and the forearm. | Biceps Curl, Hammer Curl, Preacher Curl.7 | Shoulder Flexion; elbow flexion is the bend at the arm's midpoint. | No |
| Elbow Extension | Increasing the angle between the upper arm and the forearm (straightening the arm). | Triceps Pushdown, Skull Crusher, Close-Grip Bench Press.7 | Shoulder Extension; extension of the elbow is purely the straightening of the arm. | No |
| Forearm Supination | Rotating the forearm so the palm faces upward (or forward). | Dumbbell Biceps Curl (with twist), Zottman Curl (start).29 | Shoulder External Rotation; supination happens at the forearm, not the shoulder. | No |
| Forearm Pronation | Rotating the forearm so the palm faces downward (or backward). | Pronated Wrist Curl, Reverse Curl, Zottman Curl (finish).29 | Shoulder Internal Rotation; pronation happens at the forearm, not the shoulder. | No |

### **Controlled Vocabulary: Wrist Actions**

| Name | Exercise Science Definition | Representative Exercises | Commonly Confused With | Unreliable to Classify Programmatically? |
| :---- | :---- | :---- | :---- | :---- |
| Wrist Flexion | Bending the hand toward the front of the forearm. | Wrist Curl, Reverse Biceps Curl (stabilization).29 | Forearm Pronation; flexion is a bend, whereas pronation is a rotation. | No |
| Wrist Extension | Bending the hand toward the back of the forearm. | Wrist Extension, Reverse Wrist Curl, Forearm Roller.29 | Forearm Supination; extension is a backward bend, not a rotation. | No |
| Radial Deviation | Tilting the hand toward the thumb side of the wrist. | Hammer Curl (as a stabilizer), Leverage Bar Work.23 | Wrist Extension; radial deviation occurs in the frontal plane, extension in the sagittal. | **Yes** — Almost always a purely stabilizing action; rarely the "name" of the move. |
| Ulnar Deviation | Tilting the hand toward the pinky side of the wrist. | Leverage Bar Work, Golf Swing (contextual).23 | Wrist Flexion; ulnar deviation occurs in the frontal plane, flexion in the sagittal. | **Yes** — Rare in general gym contexts; usually incidental to grip. |

The "Zottman Curl" provides a distinct example of the need for temporal joint-action tracking.29 It consists of elbow flexion with forearm supination in the concentric phase, followed by forearm pronation and elbow extension in the eccentric phase.29 A knowledge graph must be capable of mapping these actions sequentially rather than as a static set of labels.2

## **The Spinal Column: Regional Specialization and Integrity**

The spine is comprised of the cervical, thoracic, and lumbar regions, each with distinct mechanical properties.35 In resistance training, the thoracic and lumbar regions are often classified together as "trunk" or "spinal" actions, but their mobility profiles differ: the thoracic spine allows for significant rotation, while the lumbar spine is primarily designed for flexion and extension.35 Effective classification also requires distinguishing between dynamic segmental movement and "Pillar" or "Static" stabilization, where the goal is to resist joint action rather than create it.38

### **Controlled Vocabulary: Spinal (Thoracic/Lumbar) Actions**

| Name | Exercise Science Definition | Representative Exercises | Commonly Confused With | Unreliable to Classify Programmatically? |
| :---- | :---- | :---- | :---- | :---- |
| Spinal Flexion | Rounding the torso forward by decreasing the angle between vertebrae. | Crunch, Sit-Up, Hanging Leg Raise.23 | Posterior Pelvic Tilt; flexion involves the spine, while tilt involves the pelvis. | **Yes** — "Abs" exercises often combine both inseparably. |
| Spinal Extension | Arching the torso backward or returning to neutral from a flexed position. | Superman, Back Extension (GHD), Cobra Stretch.23 | Hip Extension; spinal extension involves the spine, while hip extension moves the femur. | **Yes** — "Back Extension" is often a misnomer for a "Hip Extension" exercise. |
| Spinal Lateral Flexion | Bending the torso to the side in the frontal plane. | Side Bend, Side Plank (concentric), Windmill.1 | Hip Abduction; lateral flexion is a trunk bend, not a leg lift. | No |
| Spinal Rotation | Twisting the torso around the longitudinal axis. | Russian Twist, Woodchop, Cable Rotation.26 | Hip Rotation; spinal rotation occurs at the vertebrae (mostly thoracic). | No |
| Spinal Stability (Bracing) | Resisting any movement in the spine while external forces are applied. | Plank, Dead Bug, Farmer’s Carry.38 | Spinal Extension; stability is the *absence* of movement, not a movement itself. | No |

### **Controlled Vocabulary: Cervical Spine (Neck) Actions**

The cervical spine is highly mobile and requires specific classification for "prehab" or specialized strength work.39

| Name | Exercise Science Definition | Representative Exercises | Commonly Confused With | Unreliable to Classify Programmatically? |
| :---- | :---- | :---- | :---- | :---- |
| Cervical Flexion | Bending the neck forward to bring the chin toward the chest. | Weighted Neck Flexion, Chin Tuck.39 | Craniocervical Flexion; general flexion is a large bend, the latter is a small "nod." | **Yes** — Neck training terms are often non-standard in the gym. |
| Cervical Extension | Bending the neck backward to look upward. | Weighted Neck Extension, Prone Neck Lift.43 | Scapular Elevation; shrugging is often used to cheat through neck extension. | No |
| Cervical Rotation | Turning the head to the left or right around a vertical axis. | Isometric Neck Rotation, Controlled Head Turns.44 | Spinal Rotation; cervical rotation is isolated to the neck vertebrae. | No |
| Cervical Lateral Flexion | Bending the neck toward the shoulder in the frontal plane. | Isometric Neck Side-Bend, Lateral Neck Stretch.44 | Shoulder Shrug; bringing the ear to the shoulder is a common compensation. | No |
| Cervical Retraction | Pulling the head backward while keeping the face forward (the "double chin" motion). | Chin Tuck, Neck Glide (backward phase).43 | Cervical Extension; retraction keeps the head level, extension tips it back. | **Yes** — Often poorly described as "pulling the head back." |

The programmatic classification of spinal movements is notoriously difficult because "Stability" is an isometric joint action.38 A "Plank" has no observable joint action in its static state, yet its mechanical classification is "Isometric Spinal Flexion Resistance".38 Furthermore, the "Butt Wink" at the bottom of a deep squat is a transition from Hip Flexion to Spinal Flexion, which is an unintended but frequent joint action that the knowledge graph should be able to flag as a "Fault" or "Variation".48

## **The Hip and Pelvic Girdle: The Torque Converter**

The hip joint is a deep ball-and-socket joint that manages the most significant loads in human movement.51 Its classification is often confounded by the motion of the pelvis, which can move relative to the femur (pelvic-on-femoral) or the femur can move relative to the pelvis (femoral-on-pelvic).1 The "Pelvic Tilt" is a primary example of this; an anterior pelvic tilt involves hip flexion and lumbar extension, while a posterior pelvic tilt involves hip extension and lumbar flexion.47

### **Controlled Vocabulary: Hip Joint Actions**

| Name | Exercise Science Definition | Representative Exercises | Commonly Confused With | Unreliable to Classify Programmatically? |
| :---- | :---- | :---- | :---- | :---- |
| Hip Flexion | Moving the thigh toward the torso or the torso toward the thigh. | Leg Raise, Lunge (front leg), High Knee.1 | Lumbar Flexion; hip flexion occurs at the ball-and-socket joint, not the spine. | No |
| Hip Extension | Moving the thigh away from the torso (straightening the hip). | Deadlift, Glute Bridge, Kettlebell Swing.1 | Lumbar Extension; hip extension often involves "cheating" with a lower back arch. | **Yes** — "Back Extension" vs. "Hip Extension" is a common industry naming error. |
| Hip Abduction | Moving the leg away from the midline in the frontal plane. | Clamshell, Lateral Leg Raise, Monster Walk.14 | Lateral Spinal Flexion; abduction is a leg movement, not a torso bend. | No |
| Hip Adduction | Moving the leg toward the midline in the frontal plane. | Adductor Machine, Copenhagen Plank, Sumo Squat.26 | Hip Internal Rotation; adduction is a frontal plane glide, not a rotation. | No |
| Hip External Rotation | Rotating the femur outward away from the midline around its long axis. | Fire Hydrant, Figure-4 Stretch, Clamshell.1 | Hip Abduction; many movements (like Clams) combine these simultaneously. | **Yes** — "Clamshells" are often tagged only as abduction. |
| Hip Internal Rotation | Rotating the femur inward toward the midline around its long axis. | Internal Rotation with Band, Seated 90/90 Rotation.1 | Hip Adduction; internal rotation is a rotation, not a glide toward center. | No |
| Hip Horizontal Adduction | Moving the thigh toward the midline in the transverse plane (when already flexed). | Seated Hip Adductor Machine, Crossing legs.1 | Hip Adduction; horizontal adduction requires the hip to be flexed at ![][image3]. | No |
| Hip Horizontal Abduction | Moving the thigh away from the midline in the transverse plane (when already flexed). | Seated Hip Abductor Machine, Clamshell (variation).1 | Hip Abduction; horizontal abduction requires the hip to be flexed at ![][image3]. | No |

A significant second-order insight for the knowledge graph is the role of the "Adductor Magnus" as a "Functional Extensor".51 When the hip is flexed beyond ![][image4], the adductors actually gain a mechanical advantage to assist in extension.51 This explains why "Sumo Squats" are often classified as adductor exercises despite the primary joint action being hip extension.26 Programmatic classification must account for these "Changing Lever Arms" where a muscle's function flips based on the joint angle.51

## **The Knee: A Modified Hinge with Rotational Utility**

The knee is primarily a uniaxial hinge joint (flexion/extension), but it is a "modified" hinge because it allows for accessory internal and external rotation when it is in a flexed position.41 This rotation is critical for terminal extension—the "Screw-Home Mechanism"—and for stabilizing the limb during cutting or lateral movements.54

### **Controlled Vocabulary: Knee Joint Actions**

| Name | Exercise Science Definition | Representative Exercises | Commonly Confused With | Unreliable to Classify Programmatically? |
| :---- | :---- | :---- | :---- | :---- |
| Knee Extension | Straightening the leg by increasing the angle between the femur and tibia. | Leg Extension, Squat (concentric), Quad Set.2 | Hip Extension; knee extension is limited to the straightening of the leg. | No |
| Knee Flexion | Bending the leg by decreasing the angle between the femur and tibia. | Leg Curl, Nordic Hamstring Curl, Squat (eccentric).7 | Plantarflexion; flexion is at the knee, while plantarflexion is at the ankle. | No |
| Knee Internal Rotation | Rotating the tibia (lower leg) toward the midline (only when knee is flexed). | Tibial Rotation Drill, Internal Rotation Isometric.54 | Hip Internal Rotation; tibial rotation occurs at the knee joint itself. | **Yes** — Almost never used as a primary classification in general fitness. |
| Knee External Rotation | Rotating the tibia (lower leg) away from the midline (only when knee is flexed). | Tibial Rotation Drill, External Rotation Isometric.54 | Hip External Rotation; tibial rotation occurs at the knee joint itself. | **Yes** — Same as above; usually considered a "clinical" assessment. |

In the gym, "Knee Dominant" is a common classification for exercises like the "Leg Extension" or "Split Squat".41 However, for a mechanical knowledge graph, "Dominance" is a relative term.41 A "Pistol Squat" might be classified as knee-dominant because the knee joint is enduring its maximal mechanical tolerance, even if the absolute force on the hip is higher.41

## **The Ankle, Foot, and Hallux: Tri-Planar Interaction**

The ankle complex is comprised of the talocrural (true ankle) joint and the subtalar joint.58 The talocrural joint is a pure hinge restricted to the sagittal plane, while the subtalar joint provides the inversion and eversion necessary for adapting to terrain.12 These motions often combine into "Pronation" (dorsiflexion, abduction, eversion) and "Supination" (plantarflexion, adduction, inversion).12

### **Controlled Vocabulary: Ankle and Subtalar Actions**

| Name | Exercise Science Definition | Representative Exercises | Commonly Confused With | Unreliable to Classify Programmatically? |
| :---- | :---- | :---- | :---- | :---- |
| Plantarflexion | Pointing the toes downward away from the shin (extending the ankle). | Calf Raise, Jump, Sled Press (push-off).2 | Knee Flexion; plantarflexion occurs at the ankle, not the knee. | No |
| Dorsiflexion | Pulling the toes upward toward the shin. | Tibialis Raise, Heel Walk, Squat (bottom range).14 | Knee Extension; dorsiflexion occurs at the ankle, not the knee. | No |
| Inversion | Tilting the sole of the foot inward toward the midline of the body. | Band Inversion, Balance Training.26 | Supination; inversion is the frontal-plane component of the tri-planar supination. | **Yes** — Most users cannot distinguish inversion from a "roll." |
| Eversion | Tilting the sole of the foot outward away from the midline of the body. | Band Eversion, Side Shuffle (stabilization).26 | Pronation; eversion is the frontal-plane component of the tri-planar pronation. | **Yes** — Often conflated with the complex motion of pronation. |

### **Controlled Vocabulary: Hallux (Big Toe) Actions**

The first metatarsophalangeal (MTP) joint, or hallux, is a meaningful joint for exercise classification due to its role in "Hallux Rigidus" management and lunge mechanics.65

| Name | Exercise Science Definition | Representative Exercises | Commonly Confused With | Unreliable to Classify Programmatically? |
| :---- | :---- | :---- | :---- | :---- |
| Hallux Extension | Pulling the big toe upward toward the top of the foot. | Lunge (rear foot), Toe Raise, Towel Curl.65 | Ankle Dorsiflexion; extension is at the toe joint, not the ankle. | No |
| Hallux Flexion | Curling the big toe downward toward the sole. | Towel Scrunch, Toe Point, Marble Pick-ups.62 | Ankle Plantarflexion; flexion is at the toe joint, not the ankle. | No |

A critical insight for the knowledge graph is the "Windlass Effect".58 When the hallux is extended (dorsiflexed) during the push-off phase of a lunge, it creates tension in the plantar aponeurosis, which mechanically stabilizes the arch of the foot.58 Exercises like "Lunges" should thus be tagged with "Hallux Extension" as a key stabilizer action for the trailing limb.50

## **Programmatic Classification and Taxonomic Ambiguity**

The most significant barrier to the automated classification of resistance training exercises is the inherent ambiguity of exercise nomenclature.3 A single "lexical" exercise name can represent multiple "mechanical" interpretations.3 For example, "Peeling a carrot" can be labeled as "cutting," "peeling," or "removing," depending on the observer’s focus.3 Similarly, a "Reverse Fly" can be labeled as "Shoulder Horizontal Abduction," "Scapular Retraction," or "Shoulder External Rotation".10

To address this, the controlled vocabulary must employ a "Consistency of Disambiguation" principle.69 This assumes that the true mechanical action of an exercise is the one that is most consistent across its primary training effects.69 If a "Seated Row" is primarily used to target the Rhomboids, "Scapular Retraction" is the primary label; if it is used for the Posterior Deltoid, "Shoulder Horizontal Abduction" may take precedence.10

Furthermore, the knowledge graph must account for "Unreliable" flags where joint actions are so subtle they cannot be inferred from a name alone.68 For instance, "Scapular Posterior Tipping" is essential for full overhead range of motion, but it is never explicitly named in "Overhead Press" instructions.15 These should be mapped as "Derived Actions"—actions that are mechanically required by a primary action but are not the primary driver of the exercise.15

## **Conclusion: Synthesis for Knowledge Graph Construction**

The development of a controlled vocabulary for joint actions is the prerequisite for a machine-readable knowledge graph of human movement.1 By standardizing anatomical terminology and identifying the systemic confusions between "relative" and "real" motion, practitioners can build models that accurately reflect the mechanical load of an exercise program.11 The "Unreliable" flags and "Commonly Confused" notes provided in this report serve as the primary disambiguation layer for the graph, ensuring that "lexical" noise—such as the misuse of "Back Extension" to mean "Hip Extension"—does not compromise the integrity of the data.40 Ultimately, the goal of this taxonomy is to bridge the gap between clinical anatomy and gym programming, providing a robust foundation for automated exercise classification and performance analysis.9

#### **Works cited**

1. Lesson 3: Joint Actions \- Brookbush Institute, accessed March 19, 2026, [https://brookbushinstitute.com/courses/joint-actions](https://brookbushinstitute.com/courses/joint-actions)  
2. How To Understand Joint Actions in Exercises \- Personal Trainer Courses, accessed March 19, 2026, [https://parallelcoaching.co.uk/how-to-understand-joint-actions-in-exercises](https://parallelcoaching.co.uk/how-to-understand-joint-actions-in-exercises)  
3. Handling Ambiguity in Action Recognition \- arXiv, accessed March 19, 2026, [https://arxiv.org/pdf/2210.04933](https://arxiv.org/pdf/2210.04933)  
4. Single vs. Multi-Joint Resistance Exercises: Effects on Muscle Strength and Hypertrophy, accessed March 19, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC4592763/](https://pmc.ncbi.nlm.nih.gov/articles/PMC4592763/)  
5. Multi-joint vs. Single-joint Resistance Exercises Induce a Similar Strength Increase in Trained Men: A Randomized Longitudinal Crossover Study \- PMC, accessed March 19, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC7745915/](https://pmc.ncbi.nlm.nih.gov/articles/PMC7745915/)  
6. Effects of Adding Single Joint Exercises to a Resistance Training Programme in Trained Women \- MDPI, accessed March 19, 2026, [https://www.mdpi.com/2075-4663/6/4/160](https://www.mdpi.com/2075-4663/6/4/160)  
7. Kinetic Chain Exercises: Open Versus Closed \- ISSA, accessed March 19, 2026, [https://www.issaonline.com/blog/post/kinetic-chain-exercises-open-versus-closed](https://www.issaonline.com/blog/post/kinetic-chain-exercises-open-versus-closed)  
8. Does the addition of single joint exercises to a resistance training program improve changes in performance and anthropometric measures in untrained men? \- PMC, accessed March 19, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC6317138/](https://pmc.ncbi.nlm.nih.gov/articles/PMC6317138/)  
9. Functional Resistance Training and the Kinetic Chain for Healthy Aging \- Herald Scholarly Open Access, accessed March 19, 2026, [https://www.heraldopenaccess.us/openaccess/functional-resistance-training-and-the-kinetic-chain-for-healthy-aging](https://www.heraldopenaccess.us/openaccess/functional-resistance-training-and-the-kinetic-chain-for-healthy-aging)  
10. Kinesiology of the Shoulder and Scapula \- Brookbush Institute, accessed March 19, 2026, [https://brookbushinstitute.com/articles/kinesiology-of-the-shoulder-and-scapula](https://brookbushinstitute.com/articles/kinesiology-of-the-shoulder-and-scapula)  
11. CRB – Relative from Real: Shoulder Motions \- Gray Institute, accessed March 19, 2026, [https://grayinstitute.com/blog/crb-relative-real-shoulder-motions](https://grayinstitute.com/blog/crb-relative-real-shoulder-motions)  
12. Chain Reaction Biomechanics – Relative from Real: Subtalar Joint \- Gray Institute, accessed March 19, 2026, [https://grayinstitute.com/blog/chain-reaction-biomechanics-relative-real-subtalar-joint](https://grayinstitute.com/blog/chain-reaction-biomechanics-relative-real-subtalar-joint)  
13. Knee Conditioning Program \- OrthoInfo \- AAOS, accessed March 19, 2026, [https://orthoinfo.aaos.org/en/recovery/knee-conditioning-program/](https://orthoinfo.aaos.org/en/recovery/knee-conditioning-program/)  
14. Stretches and Exercises to Strengthen Your Knees, from a PT \- HSS, accessed March 19, 2026, [https://www.hss.edu/health-library/move-better/exercises-strengthen-knees](https://www.hss.edu/health-library/move-better/exercises-strengthen-knees)  
15. Lesson 6: Joints of the Shoulder Girdle and Scapular Motion ..., accessed March 19, 2026, [https://brookbushinstitute.com/courses/joints-of-the-shoulder-girdle-and-scapular-joint-actions](https://brookbushinstitute.com/courses/joints-of-the-shoulder-girdle-and-scapular-joint-actions)  
16. Certified™: September 2025 \- A Pro's Guide to Muscle Mechanics: The Shoulders \- ACE, accessed March 19, 2026, [https://www.acefitness.org/continuing-education/certified/september-2025/8951/a-pro-s-guide-to-muscle-mechanics-the-shoulders/](https://www.acefitness.org/continuing-education/certified/september-2025/8951/a-pro-s-guide-to-muscle-mechanics-the-shoulders/)  
17. Evidence Based Shoulder Exercises \- The Prehab Guys \-, accessed March 19, 2026, [https://theprehabguys.com/evidence-based-shoulder-exercises/](https://theprehabguys.com/evidence-based-shoulder-exercises/)  
18. Important Movements and Mobility of the Shoulder Complex \- NESTA Certified, accessed March 19, 2026, [https://www.nestacertified.com/exercises-to-understand-anatomy-and-mobility-of-the-shoulder/](https://www.nestacertified.com/exercises-to-understand-anatomy-and-mobility-of-the-shoulder/)  
19. Shoulder and Scapula Actions: A Comprehensive Guide \- MindMap AI, accessed March 19, 2026, [https://mindmapai.app/mind-mapping/actions](https://mindmapai.app/mind-mapping/actions)  
20. Level Up Your Understanding of Shoulder Mechanics\! \- Antranik Kizirian, accessed March 19, 2026, [https://antranik.org/shoulder-mechanics/](https://antranik.org/shoulder-mechanics/)  
21. Shoulder Biomechanics and Exercises \- Medbridge, accessed March 19, 2026, [https://www.medbridge.com/blog/shoulder-biomechanics-and-exercises](https://www.medbridge.com/blog/shoulder-biomechanics-and-exercises)  
22. A SYSTEMATIC REVIEW OF THE EXERCISES THAT PRODUCE OPTIMAL MUSCLE RATIOS OF THE SCAPULAR STABILIZERS IN NORMAL SHOULDERS \- PMC, accessed March 19, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC4886800/](https://pmc.ncbi.nlm.nih.gov/articles/PMC4886800/)  
23. Types of Body Movements | Anatomy and Physiology I \- Lumen Learning, accessed March 19, 2026, [https://courses.lumenlearning.com/suny-ap1/chapter/types-of-body-movements/](https://courses.lumenlearning.com/suny-ap1/chapter/types-of-body-movements/)  
24. Joints and Movement Types: Understanding the Body's Hinges, accessed March 19, 2026, [https://www.ideafit.com/joints-and-movement-types-understanding-the-bodys-hinges/](https://www.ideafit.com/joints-and-movement-types-understanding-the-bodys-hinges/)  
25. Shoulder Surgery Exercise Guide \- OrthoInfo \- AAOS, accessed March 19, 2026, [https://orthoinfo.aaos.org/en/recovery/shoulder-surgery-exercise-guide/](https://orthoinfo.aaos.org/en/recovery/shoulder-surgery-exercise-guide/)  
26. Sagittal, Frontal and Transverse Body Planes: Exercises & Movements, accessed March 19, 2026, [https://blog.nasm.org/exercise-programming/sagittal-frontal-traverse-planes-explained-with-exercises?utm\_source=blog\&utm\_medium=referral\&utm\_campaign=organic\&utm\_content=ReasonsToBecomeCES](https://blog.nasm.org/exercise-programming/sagittal-frontal-traverse-planes-explained-with-exercises?utm_source=blog&utm_medium=referral&utm_campaign=organic&utm_content=ReasonsToBecomeCES)  
27. The Shoulder, Part IV \- IDEA Health & Fitness Association, accessed March 19, 2026, [https://www.ideafit.com/the-shoulder-part-iv/](https://www.ideafit.com/the-shoulder-part-iv/)  
28. Horizontal Abduction \- Brookbush Institute, accessed March 19, 2026, [https://brookbushinstitute.com/glossary/horizontal-abduction](https://brookbushinstitute.com/glossary/horizontal-abduction)  
29. Wrist and Elbow Strengthening and Stretching Exercises \- Mass General Hospital, accessed March 19, 2026, [https://www.massgeneral.org/assets/mgh/pdf/orthopaedics/sports-medicine/physical-therapy/mass-general-wrist-and-elbow-strengthening-exercises.pdf](https://www.massgeneral.org/assets/mgh/pdf/orthopaedics/sports-medicine/physical-therapy/mass-general-wrist-and-elbow-strengthening-exercises.pdf)  
30. Reducing Elbow, Wrist and Hand Injuries through Exercises | ACE Physical Therapy, accessed March 19, 2026, [https://ace-pt.org/reducing-injuries-through-elbow-wrist-and-hand-exercises/](https://ace-pt.org/reducing-injuries-through-elbow-wrist-and-hand-exercises/)  
31. Improving Elbow Range of Motion \- E3 Rehab, accessed March 19, 2026, [https://e3rehab.com/elbow-range-of-motion/](https://e3rehab.com/elbow-range-of-motion/)  
32. How To Understand Joint Actions in Exercises \- YouTube, accessed March 19, 2026, [https://www.youtube.com/watch?v=YJ8lj3QTzkk](https://www.youtube.com/watch?v=YJ8lj3QTzkk)  
33. Exercises for the elbows \- Arthritis UK, accessed March 19, 2026, [https://www.arthritis-uk.org/information-and-support/living-with-arthritis/health-and-wellbeing/exercising-with-arthritis/exercises-for-healthy-joints/exercises-for-the-elbows/](https://www.arthritis-uk.org/information-and-support/living-with-arthritis/health-and-wellbeing/exercising-with-arthritis/exercises-for-healthy-joints/exercises-for-the-elbows/)  
34. Tennis elbow no more: Practical eccentric and concentric exercises to heal the pain \- PMC, accessed March 19, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC2515258/](https://pmc.ncbi.nlm.nih.gov/articles/PMC2515258/)  
35. Thoracic Spine: What It Is, Function & Anatomy \- Cleveland Clinic, accessed March 19, 2026, [https://my.clevelandclinic.org/health/body/22460-thoracic-spine](https://my.clevelandclinic.org/health/body/22460-thoracic-spine)  
36. Understanding Spinal Anatomy: Regions of the Spine \- Cervical, Thoracic, Lumbar, Sacral, accessed March 19, 2026, [https://www.coloradospineinstitute.com/education/anatomy/spinal-regions/](https://www.coloradospineinstitute.com/education/anatomy/spinal-regions/)  
37. Understanding the Thoracic and Lumbar Spines \- Centeno-Schultz Clinic, accessed March 19, 2026, [https://centenoschultz.com/understanding-the-thoracic-and-lumbar-spines/](https://centenoschultz.com/understanding-the-thoracic-and-lumbar-spines/)  
38. Spinal-Exercise Prescription in Sport: Classifying Physical Training ..., accessed March 19, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC5094840/](https://pmc.ncbi.nlm.nih.gov/articles/PMC5094840/)  
39. Spine Conditioning Program \- OrthoInfo \- AAOS, accessed March 19, 2026, [https://orthoinfo.aaos.org/en/recovery/spine-conditioning-program/](https://orthoinfo.aaos.org/en/recovery/spine-conditioning-program/)  
40. Comparison of trunk and hip muscle activity during different degrees of lumbar and hip extension \- PMC, accessed March 19, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC4616077/](https://pmc.ncbi.nlm.nih.gov/articles/PMC4616077/)  
41. Basic Movement Patterns \- Science for Sport, accessed March 19, 2026, [https://www.scienceforsport.com/basic-movement-patterns/](https://www.scienceforsport.com/basic-movement-patterns/)  
42. JOINT TRAINING MANUAL FOR THE ARMED FORCES OF THE UNITED STATES, accessed March 19, 2026, [https://www.jcs.mil/Portals/36/Documents/Library/Manuals/m350003.pdf](https://www.jcs.mil/Portals/36/Documents/Library/Manuals/m350003.pdf)  
43. Therapeutic Exercise for Athletes With Nonspecific Neck Pain: A Current Concepts Review, accessed March 19, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC3435917/](https://pmc.ncbi.nlm.nih.gov/articles/PMC3435917/)  
44. Neck Exercises | University Orthopedics, accessed March 19, 2026, [https://universityorthopedics.com/educational\_resources/neck\_exercises.html](https://universityorthopedics.com/educational_resources/neck_exercises.html)  
45. Neck Exercises (Cervical Disc / Facet) \- Spine Plus, accessed March 19, 2026, [https://www.spineplus.co.uk/neck-exercises-cervical-disc-facet/](https://www.spineplus.co.uk/neck-exercises-cervical-disc-facet/)  
46. Exercises for neck muscle and joint problems \- NHS inform, accessed March 19, 2026, [https://www.nhsinform.scot/illnesses-and-conditions/muscle-bone-and-joints/neck-and-back-problems-and-conditions/exercises-for-neck-problems/](https://www.nhsinform.scot/illnesses-and-conditions/muscle-bone-and-joints/neck-and-back-problems-and-conditions/exercises-for-neck-problems/)  
47. Low Back Pain Response to Pelvic Tilt Position: An Observational Study of Chiropractic Patients \- PMC, accessed March 19, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC4812023/](https://pmc.ncbi.nlm.nih.gov/articles/PMC4812023/)  
48. Breaking Down the Exercises that Break Down Your Spine, accessed March 19, 2026, [https://spinehealth.org/article/breaking-down-the-exercises-that-break-down-your-spine/](https://spinehealth.org/article/breaking-down-the-exercises-that-break-down-your-spine/)  
49. A Functional Approach to Posterior Pelvic Tilt \- The Note Ninjas, accessed March 19, 2026, [https://thenoteninjas.com/blog/f/a-functional-approach-to-posterior-pelvic-tilt](https://thenoteninjas.com/blog/f/a-functional-approach-to-posterior-pelvic-tilt)  
50. the undervalued lunge | nsca, accessed March 19, 2026, [https://www.nsca.com/contentassets/24dd7222ed1b4caeb8a0a46b81bd11f3/ptq-4.4.9-the-undervalued-lunge.pdf](https://www.nsca.com/contentassets/24dd7222ed1b4caeb8a0a46b81bd11f3/ptq-4.4.9-the-undervalued-lunge.pdf)  
51. Kinesiology of the Hip: A Focus on Muscular Actions | Journal of Orthopaedic & Sports Physical Therapy \- jospt, accessed March 19, 2026, [https://www.jospt.org/doi/10.2519/jospt.2010.3025](https://www.jospt.org/doi/10.2519/jospt.2010.3025)  
52. Hip Conditioning Program \- OrthoInfo \- AAOS, accessed March 19, 2026, [https://orthoinfo.aaos.org/en/recovery/hip-conditioning-program/](https://orthoinfo.aaos.org/en/recovery/hip-conditioning-program/)  
53. Understanding Pelvic Tilt Muscles and Function \- NFPT, accessed March 19, 2026, [https://nfpt.com/understanding-pelvic-tilt-muscles-function/](https://nfpt.com/understanding-pelvic-tilt-muscles-function/)  
54. Knee Rotation Exercises \- My Rehab Connection, accessed March 19, 2026, [https://myrehabconnection.com/knee-rotation-exercises/](https://myrehabconnection.com/knee-rotation-exercises/)  
55. Effects of three types of resistance training on knee osteoarthritis: A systematic review and network meta-analysis, accessed March 19, 2026, [https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0309950](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0309950)  
56. Effects of three types of resistance training on knee osteoarthritis: A systematic review and network meta-analysis \- PMC, accessed March 19, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC11620422/](https://pmc.ncbi.nlm.nih.gov/articles/PMC11620422/)  
57. 6 Exercises to Help Your Knee Pain | St. Vincent's Medical Center, accessed March 19, 2026, [https://stvincents.org/about-us/news-press/news-detail?articleId=55094\&publicid=395](https://stvincents.org/about-us/news-press/news-detail?articleId=55094&publicid=395)  
58. Biomechanics | Ankleinfo, accessed March 19, 2026, [https://www.ankleinfo.net/biomechanics](https://www.ankleinfo.net/biomechanics)  
59. The Ankle and Subtalar Joints Flashcards \- Cram.com, accessed March 19, 2026, [https://www.cram.com/flashcards/the-ankle-and-subtalar-joints-7079655](https://www.cram.com/flashcards/the-ankle-and-subtalar-joints-7079655)  
60. Foot Pronation and Supination \- VH Dissector, accessed March 19, 2026, [https://www.vhdissector.com/lessons/surface-palpation-guide/ankle\_foot/joints/foot\_pronation\_supination.html](https://www.vhdissector.com/lessons/surface-palpation-guide/ankle_foot/joints/foot_pronation_supination.html)  
61. Subtalar Joint Anatomy, Movement & Pain | Study.com, accessed March 19, 2026, [https://study.com/academy/lesson/subtalar-joint-movement-anatomy.html](https://study.com/academy/lesson/subtalar-joint-movement-anatomy.html)  
62. 8 Exercises for Rehabilitating Loose Knee Joints, accessed March 19, 2026, [https://www.medparkhospital.com/en-US/lifestyles/8-exercises-for-ankle-instability](https://www.medparkhospital.com/en-US/lifestyles/8-exercises-for-ankle-instability)  
63. Foot and Ankle Conditioning Program \- OrthoInfo \- AAOS, accessed March 19, 2026, [https://orthoinfo.aaos.org/en/recovery/foot-and-ankle-conditioning-program/](https://orthoinfo.aaos.org/en/recovery/foot-and-ankle-conditioning-program/)  
64. Inversion vs. Everson of the Foot | Definition & Examples \- Simple Nursing, accessed March 19, 2026, [https://simplenursing.com/inversion-vs-eversion-of-the-foot-definition-examples/](https://simplenursing.com/inversion-vs-eversion-of-the-foot-definition-examples/)  
65. 5 Simple Hallux Rigidus Exercises \- Yeargain Foot & Ankle, accessed March 19, 2026, [https://dryeargain.com/hallux-rigidus-exercises/](https://dryeargain.com/hallux-rigidus-exercises/)  
66. Big Toe Pain During Lunges? Three Easy Alternatives, accessed March 19, 2026, [https://www.solvingpainwithstrength.com/blog/big-toe-pain-during-lunges-three-easy-alternatives](https://www.solvingpainwithstrength.com/blog/big-toe-pain-during-lunges-three-easy-alternatives)  
67. Hallux Rigidus: Exercises to Avoid (and Safe Alternatives) \- Orange Insoles, accessed March 19, 2026, [https://www.orangeinsoles.com/blogs/news/hallux-rigidus-exercises-to-avoid-and-safe-alternatives](https://www.orangeinsoles.com/blogs/news/hallux-rigidus-exercises-to-avoid-and-safe-alternatives)  
68. (PDF) A Classification Scheme for Applications with Ambiguous Data. \- ResearchGate, accessed March 19, 2026, [https://www.researchgate.net/publication/221534166\_A\_Classification\_Scheme\_for\_Applications\_with\_Ambiguous\_Data](https://www.researchgate.net/publication/221534166_A_Classification_Scheme_for_Applications_with_Ambiguous_Data)  
69. Learning from Ambiguous Examples \- Columbia University, accessed March 19, 2026, [http://www.cs.columbia.edu/\~andrews/pub/chpt-Z-short-proposal.pdf](http://www.cs.columbia.edu/~andrews/pub/chpt-Z-short-proposal.pdf)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABsAAAAXCAYAAAD6FjQuAAABMklEQVR4Xu2UvUpDQRCFRwyICCHY+gLaKJjWSjsrQbCyE0F8BMG8gDYKgqCllY0IYmMtiJWCaGVnqY0BtfHnjLsT5h4ziSkD94MP9py9O3tzi4iU9DNT8AV+wytYK2632ISv8A2u0J6yL+n8O5ygvV/W4K7LR5IunXadcg8vXL6Dly4vwxGXG27dQgernboqZUM7+wr6i5hxLp7k7yC+7Iayod1hXq/Cittbd+uQDUlD5l3Hlxvcn8IT+AhnXd+WBUmHd6jnoUbUd2UbHsNPOEd70dCo/zdjkgacuS4aGvU9wUM4G1Efop/tgDobMpNzM2dGuwcuIxal/dtZN5jzUs6MdnUuO6EHhlyezN256xTt9N/G2MpdT4zCr+yzpAF7hScSw5L2ruEt/IADhSdKSvqCH0eEWwdo/9muAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABsAAAAXCAYAAAD6FjQuAAABKklEQVR4Xu2UwUoCURSGDxkoKIS4Vdzma9imB3AV5c6N72Bb3yAUfIWoNgUt2pghCO0kCN0oQougNqELwf7DvSNnzswdGnfGfPDhPedc55/BOxIl/BfKcKOb4BtewDw8gjX45dtB1IFDuIQVNQuFg8LCvL60KObnMCvqS7EO5RH+kDusDa/giZox/ESaY93w4Lu8hZ/kDouiAQ9F3RTrAN7Fdg1j7uANnMKqmm25hiW7jgp7h2P4Atfkf5I/UYBPoo4KS4v63vZiob/gCtPwj8/7WnrgokvBE+MKS6n6gMy+N9V38gD7Sr4Ay+ue3TexvYytmZztPYtebLwwyYzM+yc5JbPvTPVjERbGJ5WPs2RF5m9pJ17hB5xbeT0S8zqZm1jYz4GYJSTsEb+K8FNQcwvtdwAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAUCAYAAACXtf2DAAABO0lEQVR4Xu2UTytEYRTGD0lJDSVZWltoinwBPoGNlbKQki9gNb6AjaXkO8iWslBKovy3omRvQWGF5+mcU+eeuW+TncX86pm5z+899507zb0j0uU/0Y8cIz/IQVqLtJA35ANZTmtkGzlFPpEJl1OiGw9Zn7GeuUcOQ79FTkJfRAZD3/ADbnYVFtzdhN4wl6EbtmNeeRujokM7yV+Ydy5Td+h27XgF6Qtra3xZEh3aCgvkyLzD49IHRL+P7CGPyCzFuA3kb/BsfsR63sgp+QocuK5xDH/w2DMlX2FOdIi3KlkX/YHpes2VNir5NsZE7/87ZBJ5kuqJpY1KviM86Tv0d3MZuocsM3VXwT4f+oK5DN10lhkO8dF3zpHX0B3OrYa+aa4jTdHBF3vnf1IdA6LrZ6JP/hfSU5no8ld+AaPPXzq48HZAAAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABsAAAAXCAYAAAD6FjQuAAABRUlEQVR4Xu2UvyuFYRTHj6L8iCxmmyibDFarXSmDkpLyJ1wyGawGg00GkyiTsikZRMTCakdhwvnec563c7/3eW4Zb91Pfes5n3Oe5733vu97RTq0O4OaF82v5oZ6iZrmXfOpWaYe2NNcab40E9SrWBK7SI/Xm5q3qms8as5D/aC5DPWiZiDUG2FdMSJ2od7gUCOJIaoTcMO+xjdixlnwwaCf6ltpngFw+75e0XSH3lpYV2DDva9nxO4dk/tAgP2J5ljs3s8GXwc3EcOHmjux33zXXYQPTZR8lgXJb/gRe6ISuRlQ8lnmxIZfyV+4T5QOLfkso2LDB+RP3U97XTq05Itg+Ijcmfsxrz+8ZuCeWLYCG57J8aM+T3UCboplKyal+SDUWxm3Guodd/9mXWxj+m/cbmzX6RPrXYu9Jt+aroaJDh3agj+4sl5v3Q+U/gAAAABJRU5ErkJggg==>