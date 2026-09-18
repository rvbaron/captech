/**
 * Enrollment service for handling member enrollments.
 */

export interface Member {
    memberId: string;
    name: string;
}

export class EnrollmentService {
    private members: Member[] = [];

    enroll(member: Member): boolean {
        if (!member.memberId) {
            return false;
        }
        return this.processMember(member);
    }

    private processMember(member: Member): boolean {
        this.members.push(member);
        return true;
    }
}
